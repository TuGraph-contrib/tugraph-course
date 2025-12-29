use std::sync::Arc;

use arrow::array::{ArrayRef, AsArray};
use minigu_common::data_chunk::DataChunk;

use crate::executor::utils::gen_try;
use crate::executor::{Executor, IntoExecutor};

pub struct FlattenBuilder<C> {
    child: C,
    column_indices: Vec<usize>,
}

impl<C> FlattenBuilder<C> {
    pub fn new(child: C, column_indices: Vec<usize>) -> Self {
        Self {
            child,
            column_indices,
        }
    }
}

impl<C: Executor> IntoExecutor for FlattenBuilder<C> {
    type IntoExecutor = impl Executor;

    fn into_executor(self) -> Self::IntoExecutor {
        gen move {
            let FlattenBuilder {
                child,
                column_indices,
            } = self;

            for chunk in child.into_iter() {
                let chunk = gen_try!(chunk);

                // Simple implementation: just extract values from ListArray columns
                let mut new_columns: Vec<ArrayRef> = Vec::new();

                for (idx, column) in chunk.columns().iter().enumerate() {
                    if column_indices.contains(&idx) {
                        // This is a ListArray column to flatten
                        let list_array = column.as_list::<i32>();
                        new_columns.push(list_array.values().clone());
                    } else {
                        // Keep as is
                        new_columns.push(Arc::clone(column));
                    }
                }

                let flattened_chunk = DataChunk::new(new_columns);
                yield Ok(flattened_chunk);
            }
        }
        .into_executor()
    }
}
