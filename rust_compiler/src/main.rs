mod indexer;
mod retriever;
mod assembler;

use anyhow::Result;
use crossterm::{
    event::{self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode, KeyEventKind},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{
    backend::{Backend, CrosstermBackend},
    layout::{Constraint, Direction, Layout},
    style::{Color, Style},
    widgets::{Paragraph, Wrap},
    Frame, Terminal,
};
use std::{io, process::Command, time::Duration};

use indexer::{Indexer, Index};
use retriever::Retriever;
use assembler::Assembler;

enum AppState {
    Input,
    Processing,
    Review,
}

struct App {
    input_text: String,       // Manual input buffer
    cursor_pos: usize,        // Cursor position
    messages: Vec<(String, String)>,
    state: AppState,
    indexer: Indexer,
    retriever: Retriever,
    assembler: Assembler,
    index_data: Index,
    current_code: Option<assembler::CompilerOutput>,
}

impl App {
    fn new() -> Result<Self> {
        Ok(Self {
            input_text: String::new(),
            cursor_pos: 0,
            messages: vec![
                ("System".to_string(), "Welcome to Assembly Engine!".to_string())
            ],
            state: AppState::Input,
            indexer: Indexer::new()?,
            retriever: Retriever::new(),
            assembler: Assembler::new(),
            index_data: Index::default(),
            current_code: None,
        })
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    // Setup Terminal
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen, EnableMouseCapture)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    // Create App
    let mut app = App::new()?;

    // Initial Indexing
    app.messages.push(("System".to_string(), "Indexing files...".to_string()));
    terminal.draw(|f| ui(f, &app))?;
    
    // Scan files - skip venv and src directories (index only user libraries)
    let mut count = 0;
    for entry in walkdir::WalkDir::new(".") {
        let entry = entry?;
        let path = entry.path();
        let path_str = path.to_string_lossy();
        // Skip venv, src, rust_compiler, and hidden directories
        if path.extension().is_some_and(|e| e == "py") 
            && !path_str.contains("venv") 
            && !path_str.contains("/src/")
            && !path_str.contains("rust_compiler")
            && !path_str.starts_with("./.") {
            if let Ok(_) = app.indexer.parse_file(path, &mut app.index_data) {
                count += 1;
            }
        }
    }
    
    app.indexer.save_index(&app.index_data, std::path::Path::new("inverted_index.json"))?;
    app.retriever.load_index(std::path::Path::new("inverted_index.json"))?;
    
    app.messages.push(("System".to_string(), format!("Indexed {count} files. Type a query and press Enter.")));

    // Run Loop
    let res = run_app(&mut terminal, app).await;

    // Restore Terminal
    disable_raw_mode()?;
    execute!(
        terminal.backend_mut(),
        LeaveAlternateScreen,
        DisableMouseCapture
    )?;
    terminal.show_cursor()?;

    if let Err(err) = res {
        println!("{err:?}")
    }

    Ok(())
}

async fn run_app<B: Backend>(terminal: &mut Terminal<B>, mut app: App) -> Result<()> {
    loop {
        terminal.draw(|f| ui(f, &app))?;

        if event::poll(Duration::from_millis(50))? {
            if let Event::Key(key) = event::read()? {
                // Only handle key press events (not release)
                if key.kind != KeyEventKind::Press {
                    continue;
                }
                
                match app.state {
                    AppState::Input => {
                        match key.code {
                            KeyCode::Enter => {
                                let query = app.input_text.clone();
                                if query == "exit" {
                                    return Ok(());
                                }
                                if !query.is_empty() {
                                    app.messages.push(("User".to_string(), query.clone()));
                                    app.input_text.clear();
                                    app.cursor_pos = 0;
                                    app.state = AppState::Processing;
                                    
                                    terminal.draw(|f| ui(f, &app))?;

                                    process_query(&mut app, query)?;
                                    app.state = AppState::Review;
                                }
                            }
                            KeyCode::Esc => return Ok(()),
                            KeyCode::Char(c) => {
                                app.input_text.insert(app.cursor_pos, c);
                                app.cursor_pos += 1;
                            }
                            KeyCode::Backspace => {
                                if app.cursor_pos > 0 {
                                    app.cursor_pos -= 1;
                                    app.input_text.remove(app.cursor_pos);
                                }
                            }
                            KeyCode::Delete => {
                                if app.cursor_pos < app.input_text.len() {
                                    app.input_text.remove(app.cursor_pos);
                                }
                            }
                            KeyCode::Left => {
                                if app.cursor_pos > 0 {
                                    app.cursor_pos -= 1;
                                }
                            }
                            KeyCode::Right => {
                                if app.cursor_pos < app.input_text.len() {
                                    app.cursor_pos += 1;
                                }
                            }
                            KeyCode::Home => {
                                app.cursor_pos = 0;
                            }
                            KeyCode::End => {
                                app.cursor_pos = app.input_text.len();
                            }
                            _ => {}
                        }
                    }
                    AppState::Review => {
                        match key.code {
                            KeyCode::Char('y') => {
                                if let Some(code_obj) = &app.current_code {
                                    // Get full path for output
                                    let full_path = std::env::current_dir()
                                        .map(|p| p.join(&code_obj.filename))
                                        .map(|p| p.display().to_string())
                                        .unwrap_or_else(|_| code_obj.filename.clone());
                                    
                                    std::fs::write(&code_obj.filename, &code_obj.code)?;
                                    app.messages.push(("System".to_string(), format!("Saved to: {full_path}")));
                                    
                                    let output = Command::new("venv/bin/python")
                                        .arg(&code_obj.filename)
                                        .output()?;
                                    
                                    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
                                    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
                                    
                                    let has_stdout = !stdout.is_empty();
                                    let has_stderr = !stderr.is_empty();
                                    
                                    if has_stdout {
                                        app.messages.push(("Output".to_string(), stdout));
                                    }
                                    if has_stderr {
                                        app.messages.push(("Error".to_string(), stderr));
                                    }
                                    if !has_stdout && !has_stderr {
                                        app.messages.push(("Output".to_string(), "(no output)".to_string()));
                                    }
                                }
                                app.state = AppState::Input;
                                app.current_code = None;
                            }
                            KeyCode::Char('n') | KeyCode::Esc => {
                                app.messages.push(("System".to_string(), "Discarded.".to_string()));
                                app.state = AppState::Input;
                                app.current_code = None;
                            }
                            _ => {}
                        }
                    }
                    _ => {}
                }
            }
        }
    }
}

fn process_query(app: &mut App, query: String) -> Result<()> {
    let chunks = app.retriever.search(&query);
    app.messages.push(("System".to_string(), format!("Retrieved {} chunks.", chunks.len())));
    
    match app.assembler.generate_glue_code(chunks, query) {
        Ok(output) => {
            app.messages.push(("Reasoning".to_string(), output.reasoning.clone()));
            app.messages.push(("Generated Code".to_string(), output.code.clone()));
            app.current_code = Some(output);
        }
        Err(e) => {
            app.messages.push(("Error".to_string(), format!("Assembly failed: {e}")));
        }
    }
    Ok(())
}

fn ui(f: &mut Frame, app: &App) {
    // Layout: History | Status | Spacer | Input
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Min(1),    // History
            Constraint::Length(1), // Status
            Constraint::Length(1), // Spacer
            Constraint::Length(1), // Input
        ].as_ref())
        .split(f.size());

    // 1. History Area (Scrolling)
    let msg_count = app.messages.len();
    
    // Simple logic to show last N messages that fit
    // In a real app we'd calculate exact line heights, but this is a good approximation
    let start_idx = msg_count.saturating_sub(10);

    let mut content = Vec::new();
    
    for (title, body) in app.messages.iter().skip(start_idx) {
        // Style based on type
        let (prefix, color, style) = match title.as_str() {
            "User" => (" >", Color::White, Style::default().add_modifier(ratatui::style::Modifier::BOLD)),
            "System" => (" *", Color::DarkGray, Style::default().fg(Color::DarkGray)), 
            "Reasoning" => (" ~", Color::Yellow, Style::default().fg(Color::Yellow).add_modifier(ratatui::style::Modifier::ITALIC)),
            "Generated Code" => (" #", Color::Cyan, Style::default().fg(Color::Cyan)), 
            "Output" => (" =", Color::Green, Style::default().fg(Color::LightGreen)),
            "Error" => (" !", Color::Red, Style::default().fg(Color::LightRed)),
            _ => (" ?", Color::White, Style::default()),
        };

        // Header
        content.push(ratatui::text::Line::from(vec![
            ratatui::text::Span::styled(prefix.to_string(), style),
            ratatui::text::Span::raw(" "),
            ratatui::text::Span::styled(title, style),
        ]));
        
        // Body (indented)
        for line in body.lines() {
            content.push(ratatui::text::Line::from(vec![
                ratatui::text::Span::raw("   "),
                ratatui::text::Span::styled(line, Style::default().fg(if title == "User" { Color::Reset } else { color })),
            ]));
        }
        content.push(ratatui::text::Line::from("")); // Spacer
    }

    let history = Paragraph::new(content)
        .wrap(Wrap { trim: false });
    f.render_widget(history, chunks[0]);


    // 2. Status Line (* Simmering...)
    let (status_text, status_color) = match app.state {
        AppState::Input => ("* Simmering...", Color::DarkGray),
        AppState::Processing => ("* Thinking...", Color::Yellow),
        AppState::Review => ("* Verify Execution? [y/n]", Color::LightRed),
    };
    
    let status = Paragraph::new(status_text)
        .style(Style::default().fg(status_color).add_modifier(ratatui::style::Modifier::ITALIC));
    f.render_widget(status, chunks[1]);
    
    
    // 3. Input Line
    let prefix = "> ";
    let input_text = match app.state {
        AppState::Input => app.input_text.as_str(),
        _ => "", 
    };
    
    let input_line = ratatui::text::Line::from(vec![
        ratatui::text::Span::styled(prefix, Style::default().fg(Color::White).add_modifier(ratatui::style::Modifier::BOLD)),
        ratatui::text::Span::raw(input_text),
    ]);
    
    f.render_widget(Paragraph::new(input_line), chunks[3]);

    // Cursor
    if let AppState::Input = app.state {
        f.set_cursor(
            chunks[3].x + prefix.len() as u16 + app.cursor_pos as u16,
            chunks[3].y,
        );
    }
}
