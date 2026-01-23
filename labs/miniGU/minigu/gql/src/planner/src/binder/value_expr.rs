use std::str::FromStr;

use gql_parser::ast::{
    BinaryOp, BooleanLiteral, Expr, Function, Literal, NonNegativeInteger, StringLiteral,
    StringLiteralKind, UnaryOp, UnsignedInteger, UnsignedIntegerKind, UnsignedNumericLiteral,
    Value,
};
use minigu_common::constants::SESSION_USER;
use minigu_common::data_type::LogicalType;
use minigu_common::error::not_implemented;
use minigu_common::value::{F32, F64, ScalarValue};

use smol_str::SmolStr;

use super::Binder;
use super::error::{BindError, BindResult};
use crate::bound::{BoundBinaryOp, BoundExpr, BoundExprKind, BoundUnsignedInteger};

impl Binder<'_> {
    pub fn bind_value_expression(&self, expr: &Expr) -> BindResult<BoundExpr> {
        match expr {
            Expr::Binary { left, op, right } => {
                let left_expr = self.bind_value_expression(left.value())?;
                let right_expr = self.bind_value_expression(right.value())?;
                
                let bound_op = match *op.value() {
                    BinaryOp::Add => BoundBinaryOp::Add,
                    BinaryOp::Sub => BoundBinaryOp::Sub,
                    BinaryOp::Mul => BoundBinaryOp::Mul,
                    BinaryOp::Div => BoundBinaryOp::Div,
                    BinaryOp::Concat => BoundBinaryOp::Concat,
                    BinaryOp::Or => BoundBinaryOp::Or,
                    BinaryOp::Xor => BoundBinaryOp::Xor,
                    BinaryOp::And => BoundBinaryOp::And,
                    BinaryOp::Lt => BoundBinaryOp::Lt,
                    BinaryOp::Le => BoundBinaryOp::Le,
                    BinaryOp::Gt => BoundBinaryOp::Gt,
                    BinaryOp::Ge => BoundBinaryOp::Ge,
                    BinaryOp::Eq => BoundBinaryOp::Eq,
                    BinaryOp::Ne => BoundBinaryOp::Ne,
                };
                
                // Determine result type based on operator
                let result_type = match bound_op {
                    BoundBinaryOp::And | BoundBinaryOp::Or | BoundBinaryOp::Xor |
                    BoundBinaryOp::Lt | BoundBinaryOp::Le | BoundBinaryOp::Gt |
                    BoundBinaryOp::Ge | BoundBinaryOp::Eq | BoundBinaryOp::Ne => LogicalType::Boolean,
                    BoundBinaryOp::Concat => LogicalType::String,
                    _ => left_expr.logical_type.clone(),
                };
                
                Ok(BoundExpr {
                    kind: BoundExprKind::Binary {
                        left: Box::new(left_expr),
                        op: bound_op,
                        right: Box::new(right_expr),
                    },
                    logical_type: result_type,
                    nullable: false,
                })
            }
            Expr::Unary { op, child } => {
                use crate::bound::BoundUnaryOp;
                let inner_expr = self.bind_value_expression(child.value())?;
                
                let bound_op = match *op.value() {
                    UnaryOp::Plus => BoundUnaryOp::Plus,
                    UnaryOp::Minus => BoundUnaryOp::Minus,
                    UnaryOp::Not => BoundUnaryOp::Not,
                };
                
                let result_type = match bound_op {
                    BoundUnaryOp::Not => LogicalType::Boolean,
                    _ => inner_expr.logical_type.clone(),
                };
                
                Ok(BoundExpr {
                    kind: BoundExprKind::Unary {
                        op: bound_op,
                        expr: Box::new(inner_expr),
                    },
                    logical_type: result_type,
                    nullable: false,
                })
            }
            Expr::DurationBetween { .. } => not_implemented("duration between expression", None),
            Expr::Is { .. } => not_implemented("is expression", None),
            Expr::IsNot { .. } => not_implemented("is not expression", None),
            Expr::Function(function) => self.bind_function_expression(function),
            Expr::Aggregate(_) => not_implemented("aggregate expression", None),
            Expr::Variable(variable) => {
                let field = self
                    .active_data_schema
                    .as_ref()
                    .ok_or_else(|| BindError::VariableNotFound(variable.clone()))?
                    .get_field_by_name(variable)
                    .ok_or_else(|| BindError::VariableNotFound(variable.clone()))?;
                Ok(BoundExpr::variable(
                    variable.to_string(),
                    field.ty().clone(),
                    field.is_nullable(),
                ))
            }
            Expr::Value(value) => bind_value(value),
            Expr::Path(_) => not_implemented("path expression", None),
            Expr::Property { source, trailing_names } => {
                // 假设 source 是 Variable，trailing_names 只有一个元素
                if let Expr::Variable(var) = source.value() {
                    if trailing_names.len() != 1 {
                        return not_implemented("multi-level property access", None);
                    }
                    let variable = var.to_string();
                    let property_name = trailing_names[0].value().to_string();
                    
                    // 从 schema 获取变量的类型信息
                    let schema = self
                        .active_data_schema
                        .as_ref()
                        .ok_or_else(|| BindError::VariableNotFound(SmolStr::from(&variable)))?;
                    
                    // 获取变量的字段信息（在 Match 绑定时已添加）
                    let var_field = schema
                        .get_field_by_name(&variable)
                        .ok_or_else(|| BindError::VariableNotFound(SmolStr::from(&variable)))?;
                    
                    // 从 Vertex 类型中获取属性类型
                    let property_type = if let LogicalType::Vertex(vertex_fields) = var_field.ty() {
                        if !vertex_fields.is_empty() {
                            // 属性列表不为空，直接查找
                            vertex_fields
                                .iter()
                                .find(|f| f.name() == property_name)
                                .map(|f| f.ty().clone())
                                .ok_or_else(|| BindError::VariableNotFound(SmolStr::from(&property_name)))?
                        } else {
                            // 属性列表为空（如 Expand 的目标顶点），尝试从 catalog 获取
                            // 获取变量的标签信息
                            let var_labels = schema.get_var_label(&variable);
                            if let Some(labels) = var_labels {
                                // 尝试从 catalog 获取属性类型
                                self.get_property_type_from_catalog(&property_name, &labels)?
                            } else {
                                // 没有标签信息，使用默认类型（String）
                                LogicalType::String
                            }
                        }
                    } else {
                        return Err(BindError::VariableNotFound(SmolStr::from(&property_name)));
                    };
                    
                    Ok(BoundExpr {
                        kind: BoundExprKind::Property {
                            variable,
                            property: property_name,
                        },
                        logical_type: property_type,
                        nullable: false, // 假设属性不为空
                    })
                } else {
                    not_implemented("complex property expression", None)
                }
            }
            Expr::Graph(_) => not_implemented("graph expression", None),
        }
    }

    fn bind_function_expression(&self, function: &Function) -> BindResult<BoundExpr> {
        match function {
            Function::Generic(generic) => {
                let func_name = generic.name.value().to_lowercase();
                match func_name.as_str() {
                    "id" => {
                        // id(n) 函数：返回顶点的 ID
                        if generic.args.len() != 1 {
                            return Err(BindError::InvalidFunctionArgs("id".to_string()));
                        }
                        let arg = &generic.args[0];
                        let bound_arg = self.bind_value_expression(arg.value())?;
                        
                        // id() 函数返回 Int64 类型
                        Ok(BoundExpr {
                            kind: BoundExprKind::Function {
                                name: "id".to_string(),
                                args: vec![bound_arg],
                            },
                            logical_type: LogicalType::Int64,
                            nullable: false,
                        })
                    }
                    _ => not_implemented(&format!("function: {}", func_name), None),
                }
            }
            Function::Numeric(_) => not_implemented("numeric function expression", None),
            Function::Case(_) => not_implemented("case function expression", None),
        }
    }

    /// 从 catalog 获取属性类型
    fn get_property_type_from_catalog(
        &self,
        property_name: &str,
        labels: &[Vec<minigu_common::types::LabelId>],
    ) -> BindResult<LogicalType> {
        use minigu_catalog::label_set::LabelSet;
        
        // 尝试从当前图的类型信息获取属性类型
        if let Some(graph_ref) = &self.current_graph {
            let graph_type = graph_ref.graph_type();
            // 遍历所有可能的标签组合
            for label_group in labels {
                if label_group.is_empty() {
                    continue;
                }
                let label_set = LabelSet::from_iter(label_group.clone());
                if let Ok(Some(vertex_type)) = graph_type.get_vertex_type(&label_set) {
                    // 在顶点类型中查找属性
                    for (_, property) in vertex_type.properties() {
                        if property.name() == property_name {
                            return Ok(property.logical_type().clone());
                        }
                    }
                }
            }
        }
        
        // 如果找不到，返回默认的 String 类型
        Ok(LogicalType::String)
    }

    pub fn bind_non_negative_integer(
        &self,
        integer: &NonNegativeInteger,
    ) -> BindResult<BoundUnsignedInteger> {
        match integer {
            NonNegativeInteger::Integer(unsigned) => bind_unsigned_integer(unsigned),
            NonNegativeInteger::Parameter(_) => {
                not_implemented("parameterized non-negative integer", None)
            }
        }
    }
}

pub fn bind_binary_op(op: &BinaryOp) -> BoundBinaryOp {
    match op {
        BinaryOp::Add => BoundBinaryOp::Add,
        BinaryOp::Sub => BoundBinaryOp::Sub,
        BinaryOp::Mul => BoundBinaryOp::Mul,
        BinaryOp::Div => BoundBinaryOp::Div,
        BinaryOp::Concat => BoundBinaryOp::Concat,
        BinaryOp::Or => BoundBinaryOp::Or,
        BinaryOp::Xor => BoundBinaryOp::Xor,
        BinaryOp::And => BoundBinaryOp::And,
        BinaryOp::Lt => BoundBinaryOp::Lt,
        BinaryOp::Le => BoundBinaryOp::Le,
        BinaryOp::Gt => BoundBinaryOp::Gt,
        BinaryOp::Ge => BoundBinaryOp::Ge,
        BinaryOp::Eq => BoundBinaryOp::Eq,
        BinaryOp::Ne => BoundBinaryOp::Ne,
    }
}

pub fn bind_value(value: &Value) -> BindResult<BoundExpr> {
    match value {
        Value::SessionUser => Ok(BoundExpr::value(
            SESSION_USER.into(),
            LogicalType::String,
            false,
        )),
        Value::Parameter(_) => not_implemented("parameter value", None),
        Value::Literal(literal) => bind_literal(literal),
    }
}

pub fn bind_literal(literal: &Literal) -> BindResult<BoundExpr> {
    match literal {
        Literal::Numeric(literal) => bind_numeric_literal(literal),
        Literal::Boolean(literal) => Ok(bind_boolean_literal(literal)),
        Literal::String(literal) => bind_string_literal(literal),
        Literal::Temporal(_) => not_implemented("temporal literal", None),
        Literal::Duration(_) => not_implemented("duration literal", None),
        Literal::List(_) => not_implemented("list literal", None),
        Literal::Record(_) => not_implemented("record literal", None),
        Literal::Null => Ok(BoundExpr::value(ScalarValue::Null, LogicalType::Null, true)),
    }
}

pub fn bind_numeric_literal(literal: &UnsignedNumericLiteral) -> BindResult<BoundExpr> {
    match literal {
        UnsignedNumericLiteral::Integer(integer) => {
            let unsigned = bind_unsigned_integer(integer.value())?;
            let expr = match unsigned {
                BoundUnsignedInteger::Int8(value) => {
                    BoundExpr::value(value.into(), LogicalType::Int8, false)
                }
                BoundUnsignedInteger::Int16(value) => {
                    BoundExpr::value(value.into(), LogicalType::Int16, false)
                }
                BoundUnsignedInteger::Int32(value) => {
                    BoundExpr::value(value.into(), LogicalType::Int32, false)
                }
                BoundUnsignedInteger::Int64(value) => {
                    BoundExpr::value(value.into(), LogicalType::Int64, false)
                }
            };
            Ok(expr)
        }
        UnsignedNumericLiteral::Float(float) => {
            let literal = float.value().float.as_str();
            let parsed = literal
                .parse::<f64>()
                .map_err(|_| BindError::InvalidFloatLiteral(literal.to_string()))?;
            Ok(BoundExpr::value(
                ScalarValue::Float64(Some(F64::from(parsed))),
                LogicalType::Float64,
                false,
            ))
        }
    }
}

pub fn bind_unsigned_integer(integer: &UnsignedInteger) -> BindResult<BoundUnsignedInteger> {
    match integer.kind {
        UnsignedIntegerKind::Binary => not_implemented("binary integer literal", None),
        UnsignedIntegerKind::Octal => not_implemented("octal integer literal", None),
        UnsignedIntegerKind::Decimal => {
            if let Ok(value) = integer.integer.parse::<i8>() {
                Ok(BoundUnsignedInteger::Int8(value))
            } else if let Ok(value) = integer.integer.parse::<i16>() {
                Ok(BoundUnsignedInteger::Int16(value))
            } else if let Ok(value) = integer.integer.parse::<i32>() {
                Ok(BoundUnsignedInteger::Int32(value))
            } else if let Ok(value) = integer.integer.parse::<i64>() {
                Ok(BoundUnsignedInteger::Int64(value))
            } else {
                Err(BindError::InvalidInteger(integer.integer.clone()))
            }
        }
        UnsignedIntegerKind::Hex => not_implemented("hex integer literal", None),
    }
}

pub fn bind_boolean_literal(literal: &BooleanLiteral) -> BoundExpr {
    match literal {
        BooleanLiteral::True => BoundExpr::value(true.into(), LogicalType::Boolean, false),
        BooleanLiteral::False => BoundExpr::value(false.into(), LogicalType::Boolean, false),
        // TODO: Is it OK to treat `unknown` as `null` here?
        BooleanLiteral::Unknown => {
            BoundExpr::value(ScalarValue::Boolean(None), LogicalType::Boolean, true)
        }
    }
}

pub fn bind_string_literal(literal: &StringLiteral) -> BindResult<BoundExpr> {
    match literal.kind {
        StringLiteralKind::Char => Ok(BoundExpr::value(
            literal.literal.as_str().into(),
            LogicalType::String,
            false,
        )),
        StringLiteralKind::Byte => not_implemented("byte string literal", None),
    }
}
