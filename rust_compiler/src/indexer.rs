use anyhow::{Result, Context};
use serde::{Serialize, Deserialize};
use std::collections::HashMap;
use std::fs;
use std::path::Path;
use tree_sitter::{Parser, Query, QueryCursor};

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct Chunk {
    pub source: String,
    pub filename: String,
    pub func_name: String,
}

#[derive(Serialize, Deserialize, Debug, Default)]
pub struct Index {
    pub chunks: HashMap<String, Chunk>,
}

pub struct Indexer {
    parser: Parser,
    query: Query,
}

impl Indexer {
    pub fn new() -> Result<Self> {
        let mut parser = Parser::new();
        let language = tree_sitter_python::language();
        parser.set_language(language)
            .map_err(|e| anyhow::anyhow!("Failed to set language: {e}"))?;

        let query_scm = "
        (function_definition
          name: (identifier) @name) @function
        (class_definition
          name: (identifier) @name) @class
        ";
        let query = Query::new(language, query_scm)
            .map_err(|e| anyhow::anyhow!("Failed to compile query: {e}"))?;

        Ok(Self { parser, query })
    }

    pub fn parse_file(&mut self, path: &Path, index: &mut Index) -> Result<()> {
        let source_code = fs::read_to_string(path)
            .with_context(|| format!("Failed to read file: {path:?}"))?;
        
        let filename = path.file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("unknown")
            .to_string();

        let tree = self.parser.parse(&source_code, None)
            .ok_or_else(|| anyhow::anyhow!("Failed to parse code"))?;

        let mut cursor = QueryCursor::new();
        // tree-sitter 0.20 API usage
        let matches = cursor.matches(&self.query, tree.root_node(), source_code.as_bytes());

        for m in matches {
            // Find the @name capture and the @function/@class capture
            let mut func_name = String::new();
            let mut node_byte_range = 0..0;
            
            for capture in m.captures {
                let capture_name = &self.query.capture_names()[capture.index as usize];
                if capture_name == "name" {
                    func_name = capture.node.utf8_text(source_code.as_bytes())?.to_string();
                } else if capture_name == "function" || capture_name == "class" {
                    node_byte_range = capture.node.byte_range();
                }
            }

            if !func_name.is_empty() && node_byte_range.end > node_byte_range.start {
                let chunk_source = &source_code[node_byte_range];
                index.chunks.insert(func_name.clone(), Chunk {
                    source: chunk_source.to_string(),
                    filename: filename.clone(),
                    func_name,
                });
            }
        }
        Ok(())
    }

    pub fn save_index(&self, index: &Index, path: &Path) -> Result<()> {
        let file = fs::File::create(path)?;
        serde_json::to_writer_pretty(file, &index.chunks)?;
        Ok(())
    }
}
