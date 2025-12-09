use anyhow::{Result, Context};
use serde::{Serialize, Deserialize};
use std::process::{Command, Stdio};
use std::io::Write;
use std::path::PathBuf;
use crate::indexer::Chunk;

#[derive(Serialize)]
struct BridgeRequest {
    chunks: Vec<Chunk>,
    query: String,
}

#[derive(Deserialize, Debug, Clone)]
pub struct CompilerOutput {
    pub reasoning: String,
    pub code: String,
    pub filename: String,
}

pub struct Assembler {
    python_path: String,
    bridge_script: PathBuf,
}

impl Assembler {
    pub fn new() -> Self {
        // Try to find Python interpreter
        let python_path = Self::find_python().unwrap_or_else(|| "python3".to_string());
        
        // Bridge script should be next to the binary or in current dir
        let bridge_script = Self::find_bridge_script();
        
        Self { python_path, bridge_script }
    }
    
    fn find_python() -> Option<String> {
        // Priority order: venv, python3, python
        for path in &["venv/bin/python", "python3", "python"] {
            if Command::new(path).arg("--version").output().is_ok() {
                return Some(path.to_string());
            }
        }
        None
    }
    
    fn find_bridge_script() -> PathBuf {
        // Try multiple locations
        for path in &[
            "assembler_bridge.py",           // Same directory as binary
            "src/assembler_bridge.py",       // Development location
            ".assembly_engine/bridge.py",    // Hidden config dir
        ] {
            let p = PathBuf::from(path);
            if p.exists() {
                return p;
            }
        }
        // Default to src location
        PathBuf::from("src/assembler_bridge.py")
    }

    pub fn generate_glue_code(&self, chunks: Vec<Chunk>, query: String) -> Result<CompilerOutput> {
        if !self.bridge_script.exists() {
            anyhow::bail!(
                "Bridge script not found. Please ensure '{}' exists.\n\
                 You can copy it from the Assembly Engine source.",
                self.bridge_script.display()
            );
        }

        let mut child = Command::new(&self.python_path)
            .arg(&self.bridge_script)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .context(format!("Failed to spawn python ({})", self.python_path))?;

        let request = BridgeRequest { chunks, query };
        let json_input = serde_json::to_string(&request)?;

        if let Some(mut stdin) = child.stdin.take() {
            stdin.write_all(json_input.as_bytes())?;
        }

        let output = child.wait_with_output()?;
        
        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            anyhow::bail!("Python bridge failed: {}", stderr);
        }

        let output_str = String::from_utf8(output.stdout)?;
        let result: CompilerOutput = serde_json::from_str(&output_str)
            .context("Failed to parse bridge output")?;

        Ok(result)
    }
}

