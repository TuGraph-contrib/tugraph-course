use std::sync::Arc;

use arrow::array::{ArrayRef, AsArray};
use arrow::compute::kernels::{boolean, cast, cmp, numeric};
use arrow::datatypes::DataType;
use minigu_common::data_chunk::DataChunk;

use super::{DatumRef, Evaluator};
use crate::error::ExecutionResult;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BinaryOp {
    Add,
    Sub,
    Mul,
    Div,
    Rem,
    And,
    Or,
    Eq,
    Ne,
    Gt,
    Ge,
    Lt,
    Le,
}

#[derive(Debug)]
pub struct Binary<L, R> {
    op: BinaryOp,
    left: L,
    right: R,
}

impl<L, R> Binary<L, R> {
    pub fn new(op: BinaryOp, left: L, right: R) -> Self {
        Self { op, left, right }
    }
}

/// Coerce two arrays to compatible types for comparison and handle scalar broadcasting
fn coerce_for_comparison(left: &ArrayRef, right: &ArrayRef) -> (ArrayRef, ArrayRef) {
    // Handle length mismatch (scalar broadcasting)
    let (left_broadcast, right_broadcast) = if left.len() != right.len() {
        if left.len() == 1 && right.len() > 1 {
            // Left is scalar, need to broadcast
            let repeated = repeat_scalar(left, right.len());
            (repeated, right.clone())
        } else if right.len() == 1 && left.len() > 1 {
            // Right is scalar, need to broadcast
            let repeated = repeat_scalar(right, left.len());
            (left.clone(), repeated)
        } else {
            (left.clone(), right.clone())
        }
    } else {
        (left.clone(), right.clone())
    };
    
    let left_type = left_broadcast.data_type();
    let right_type = right_broadcast.data_type();
    
    if left_type == right_type {
        return (left_broadcast, right_broadcast);
    }
    
    // If both are integer types, cast to wider type
    let target_type = get_wider_type(left_type, right_type);
    
    let left_cast = if left_type != &target_type {
        cast::cast(&left_broadcast, &target_type).unwrap_or_else(|_| left_broadcast.clone())
    } else {
        left_broadcast
    };
    
    let right_cast = if right_type != &target_type {
        cast::cast(&right_broadcast, &target_type).unwrap_or_else(|_| right_broadcast.clone())
    } else {
        right_broadcast
    };
    
    (left_cast, right_cast)
}

/// Repeat a scalar array n times
fn repeat_scalar(scalar: &ArrayRef, n: usize) -> ArrayRef {
    use arrow::array::*;
    use arrow::datatypes::DataType;
    
    match scalar.data_type() {
        DataType::Int8 => {
            let arr = scalar.as_primitive::<arrow::datatypes::Int8Type>();
            let val = arr.value(0);
            Arc::new(Int8Array::from(vec![val; n]))
        }
        DataType::Int16 => {
            let arr = scalar.as_primitive::<arrow::datatypes::Int16Type>();
            let val = arr.value(0);
            Arc::new(Int16Array::from(vec![val; n]))
        }
        DataType::Int32 => {
            let arr = scalar.as_primitive::<arrow::datatypes::Int32Type>();
            let val = arr.value(0);
            Arc::new(Int32Array::from(vec![val; n]))
        }
        DataType::Int64 => {
            let arr = scalar.as_primitive::<arrow::datatypes::Int64Type>();
            let val = arr.value(0);
            Arc::new(Int64Array::from(vec![val; n]))
        }
        DataType::Utf8 => {
            let arr = scalar.as_string::<i32>();
            let val = arr.value(0);
            Arc::new(StringArray::from(vec![val; n]))
        }
        _ => scalar.clone(),
    }
}

/// Get the wider numeric type
fn get_wider_type(left: &DataType, right: &DataType) -> DataType {
    use DataType::*;
    match (left, right) {
        // Integer type promotion
        (Int8, Int16) | (Int16, Int8) => Int16,
        (Int8, Int32) | (Int32, Int8) => Int32,
        (Int8, Int64) | (Int64, Int8) => Int64,
        (Int16, Int32) | (Int32, Int16) => Int32,
        (Int16, Int64) | (Int64, Int16) => Int64,
        (Int32, Int64) | (Int64, Int32) => Int64,
        // Default to Int64
        (Int8, _) | (_, Int8) => Int64,
        (Int16, _) | (_, Int16) => Int64,
        (Int32, _) | (_, Int32) => Int64,
        _ => left.clone(),
    }
}

impl<L: Evaluator, R: Evaluator> Evaluator for Binary<L, R> {
    fn evaluate(&self, chunk: &DataChunk) -> ExecutionResult<DatumRef> {
        let left = self.left.evaluate(chunk)?;
        let right = self.right.evaluate(chunk)?;
        let array = match self.op {
            BinaryOp::Add => numeric::add(&left, &right)?,
            BinaryOp::Sub => numeric::sub(&left, &right)?,
            BinaryOp::Mul => numeric::mul(&left, &right)?,
            BinaryOp::Div => numeric::div(&left, &right)?,
            BinaryOp::Rem => numeric::rem(&left, &right)?,
            BinaryOp::And | BinaryOp::Or => {
                let left = left.as_array().as_boolean();
                let right = right.as_array().as_boolean();
                match self.op {
                    BinaryOp::And => Arc::new(boolean::and_kleene(left, right)?),
                    BinaryOp::Or => Arc::new(boolean::or_kleene(left, right)?),
                    _ => unreachable!(),
                }
            }
            BinaryOp::Eq | BinaryOp::Ne | BinaryOp::Gt | BinaryOp::Ge | BinaryOp::Lt | BinaryOp::Le => {
                // Perform type conversion for comparison operations
                let (left_coerced, right_coerced) = coerce_for_comparison(left.as_array(), right.as_array());
                match self.op {
                    BinaryOp::Eq => Arc::new(cmp::eq(&left_coerced, &right_coerced)?),
                    BinaryOp::Ne => Arc::new(cmp::neq(&left_coerced, &right_coerced)?),
                    BinaryOp::Gt => Arc::new(cmp::gt(&left_coerced, &right_coerced)?),
                    BinaryOp::Ge => Arc::new(cmp::gt_eq(&left_coerced, &right_coerced)?),
                    BinaryOp::Lt => Arc::new(cmp::lt(&left_coerced, &right_coerced)?),
                    BinaryOp::Le => Arc::new(cmp::lt_eq(&left_coerced, &right_coerced)?),
                    _ => unreachable!(),
                }
            }
        };
        Ok(DatumRef::new(array, left.is_scalar() && right.is_scalar()))
    }
}

#[cfg(test)]
mod tests {
    use arrow::array::{ArrayRef, create_array};
    use minigu_common::data_chunk;

    use super::*;
    use crate::evaluator::column_ref::ColumnRef;
    use crate::evaluator::constant::Constant;

    #[test]
    fn test_binary_1() {
        let chunk = data_chunk!((Int32, [1, 2, 3]), (Utf8, ["a", "b", "c"]));
        // c0 + c0
        let c0_add_c0 = ColumnRef::new(0).add(ColumnRef::new(0));
        let result = c0_add_c0.evaluate(&chunk).unwrap();
        let expected: ArrayRef = create_array!(Int32, [2, 4, 6]);
        assert_eq!(result.as_array(), &expected);
    }

    #[test]
    fn test_binary_2() {
        let chunk = data_chunk!((Int32, [Some(1), Some(2), None]), (Utf8, ["a", "b", "c"]));
        // c0 * 3
        let c0_add_3 = ColumnRef::new(0).mul(Constant::new(3i32.into()));
        let result = c0_add_3.evaluate(&chunk).unwrap();
        let expected: ArrayRef = create_array!(Int32, [Some(3), Some(6), None]);
        assert_eq!(result.as_array(), &expected);
    }

    #[test]
    fn test_binary_3() {
        let chunk = data_chunk!((Int32, [1, 2, 3]), (Utf8, ["a", "b", "c"]));
        // c0 + c1
        let c0_add_c1 = ColumnRef::new(0).add(ColumnRef::new(1));
        assert!(c0_add_c1.evaluate(&chunk).is_err());
    }

    #[test]
    fn test_binary_4() {
        let chunk = data_chunk!(
            (Int32, [1, 2, 3]),
            (Int32, [None, Some(4), Some(6)]),
            (Int32, [Some(3), None, Some(8)])
        );
        // c0 + c1 <= c2
        let c0_add_c1_le_c2 = ColumnRef::new(0)
            .add(ColumnRef::new(1))
            .le(ColumnRef::new(2));
        let result = c0_add_c1_le_c2.evaluate(&chunk).unwrap();
        let expected: ArrayRef = create_array!(Boolean, [None, None, Some(false)]);
        assert_eq!(result.as_array(), &expected);
    }

    /// Test three-valued logic.
    #[test]
    fn test_binary_5() {
        let chunk = data_chunk!(
            (Boolean, [Some(true), None, Some(false), None, None]),
            (Boolean, [Some(true), None, None, Some(true), Some(false)]),
            (Boolean, [
                Some(false),
                Some(true),
                None,
                Some(false),
                Some(false)
            ])
        );
        // c0 AND c1 OR c2
        let c0_and_c1_or_c2 = ColumnRef::new(0)
            .and(ColumnRef::new(1))
            .or(ColumnRef::new(2));
        let result = c0_and_c1_or_c2.evaluate(&chunk).unwrap();
        let expected: ArrayRef =
            create_array!(Boolean, [Some(true), Some(true), None, None, Some(false)]);
        assert_eq!(result.as_array(), &expected);
    }

    #[test]
    fn test_binary_6() {
        let chunk = data_chunk!((Int32, [Some(1), Some(2), None]));
        // c0 * 3 + (1 + 1)
        let c0_mul_3_plus_2 = ColumnRef::new(0)
            .mul(Constant::new(3i32.into()))
            .add(Constant::new(1i32.into()).add(Constant::new(1i32.into())));
        let result = c0_mul_3_plus_2.evaluate(&chunk).unwrap();
        let expected: ArrayRef = create_array!(Int32, [Some(5), Some(8), None]);
        assert_eq!(result.as_array(), &expected);
    }
}