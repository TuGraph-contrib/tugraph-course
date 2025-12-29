use std::collections::HashMap;
use std::sync::Arc;

use arrow::array::{Array, ArrayRef, StringArray};
use minigu_common::types::{PropertyId, VertexId, VertexIdArray};

use super::{ExpandSource, VertexPropertySource};
use crate::error::ExecutionResult;

type AdjList = Arc<(Vec<VertexId>, Vec<String>)>;

/// A mock expand source that maps each vertex to its neighbors and the corresponding String-typed
/// edge properties.
///
/// This should be used for testing purposes only.
#[derive(Debug, Clone)]
pub struct MockExpandSource {
    adj_lists: HashMap<VertexId, AdjList>,
    max_array_size: usize,
}

pub struct ExpandIter {
    neighbors_props: AdjList,
    offset: usize,
    max_array_size: usize,
}

impl Iterator for ExpandIter {
    type Item = ExecutionResult<Vec<ArrayRef>>;

    fn next(&mut self) -> Option<Self::Item> {
        let (neighbors, props) = &*self.neighbors_props;
        if self.offset >= neighbors.len() {
            return None;
        }
        let neighbors = VertexIdArray::from_iter_values(
            neighbors
                .iter()
                .skip(self.offset)
                .take(self.max_array_size)
                .copied(),
        );
        let props =
            StringArray::from_iter_values(props.iter().skip(self.offset).take(self.max_array_size));
        self.offset += self.max_array_size;
        Some(Ok(vec![Arc::new(neighbors), Arc::new(props)]))
    }
}

impl ExpandSource for MockExpandSource {
    type ExpandIter = ExpandIter;

    fn expand_from_vertex(
        &self,
        vertex: VertexId,
        _edge_labels: Option<Vec<Vec<minigu_common::types::LabelId>>>,
        _target_vertex_labels: Option<Vec<Vec<minigu_common::types::LabelId>>>,
    ) -> Option<Self::ExpandIter> {
        // Mock implementation ignores label filters for simplicity
        self.adj_lists.get(&vertex).map(|adj_list| ExpandIter {
            neighbors_props: adj_list.clone(),
            offset: 0,
            max_array_size: self.max_array_size,
        })
    }
}

#[derive(Debug, Clone)]
pub struct MockVertexPropertySource {
    vertex_properties: HashMap<VertexId, String>,
}

impl MockVertexPropertySource {
    pub fn new() -> Self {
        Self {
            vertex_properties: HashMap::new(),
        }
    }

    pub fn add_vertex_property(&mut self, vertex: VertexId, property: String) {
        self.vertex_properties.insert(vertex, property);
    }
}

impl VertexPropertySource for MockVertexPropertySource {
    fn scan_vertex_properties(
        &self,
        vertices: &VertexIdArray,
        _property_id: &[PropertyId],
    ) -> ExecutionResult<Vec<ArrayRef>> {
        assert!(!vertices.is_nullable());
        let properties = StringArray::from_iter(
            vertices
                .values()
                .iter()
                .map(|v| self.vertex_properties.get(v)),
        );
        Ok(vec![Arc::new(properties)])
    }
}
