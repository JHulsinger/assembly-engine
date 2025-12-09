use anyhow::{Result, Context};
use std::collections::HashMap;
use std::fs;
use std::path::Path;
use crate::indexer::Chunk; // Assume Chunk is public in indexer

pub struct Retriever {
    index: HashMap<String, Chunk>,
}

impl Retriever {
    pub fn new() -> Self {
        Self { index: HashMap::new() }
    }

    pub fn load_index(&mut self, path: &Path) -> Result<()> {
        if !path.exists() {
            // Return empty if no index
            return Ok(());
        }
        let file = fs::File::open(path).with_context(|| "Failed to open index file")?;
        self.index = serde_json::from_reader(file)?;
        Ok(())
    }

    pub fn search(&self, query: &str) -> Vec<Chunk> {
        let tokens: Vec<String> = query.split_whitespace()
            .map(|s| s.to_lowercase())
            .filter(|s| s.len() > 3)
            .collect();

        if tokens.is_empty() {
            return Vec::new();
        }

        let mut results = Vec::new();

        for chunk in self.index.values() {
            let source_lower = chunk.source.to_lowercase();
            let matches_any = tokens.iter().any(|t| source_lower.contains(t));
            
            if matches_any {
                results.push(chunk.clone());
            }
        }
        
        results
    }
}
