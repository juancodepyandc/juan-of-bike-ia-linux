import { describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION } from '../services/codeArchitecturePlan.ts'
import { executeCodeGenerationQueue } from '../services/codeGenerationExecutor.ts'
import { buildGenerationQueueFromArchitecturePlan } from '../services/codeGenerationQueue.ts'
import type { CodeFile } from '../services/codeOrchestrator.ts'

function nextMetaFactory() {
  let sequence = 0
  return () => ({ runId: 60, sequence: ++sequence, timestamp: 1_700_000_060_000 + sequence })
}

function languageForPath(path: string) {
  if (path.endsWith('.toml')) return 'toml'
  if (path.endsWith('.rs')) return 'rust'
  if (path.endsWith('.md')) return 'markdown'
  return 'text'
}

function compilerFiles() {
  const files = new Map<string, string>()
  files.set('Cargo.toml', `[package]
name = "aurora-mini-compiler-proof"
version = "0.1.0"
edition = "2021"

[lib]
name = "aurora_mini_compiler"
path = "src/lib.rs"
`)
  files.set('src/lib.rs', `pub mod eval;
pub mod lexer;
pub mod parser;

pub use eval::eval;
pub use lexer::{lex, Token};
pub use parser::{parse, Expr};

pub fn compile_and_run(source: &str) -> Result<i64, String> {
    let tokens = lex(source)?;
    let expr = parse(&tokens)?;
    Ok(eval(&expr))
}
`)
  files.set('src/lexer.rs', `#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Token {
    Number(i64),
    Plus,
    Star,
    LParen,
    RParen,
}

pub fn lex(input: &str) -> Result<Vec<Token>, String> {
    let chars: Vec<char> = input.chars().collect();
    let mut tokens = Vec::new();
    let mut index = 0;
    while index < chars.len() {
        match chars[index] {
            '0'..='9' => {
                let start = index;
                while index < chars.len() && chars[index].is_ascii_digit() {
                    index += 1;
                }
                let value: i64 = chars[start..index].iter().collect::<String>().parse().map_err(|_| "invalid number")?;
                tokens.push(Token::Number(value));
                continue;
            }
            '+' => tokens.push(Token::Plus),
            '*' => tokens.push(Token::Star),
            '(' => tokens.push(Token::LParen),
            ')' => tokens.push(Token::RParen),
            char if char.is_whitespace() => {}
            other => return Err(format!("unexpected character: {other}")),
        }
        index += 1;
    }
    Ok(tokens)
}
`)
  files.set('src/parser.rs', `use crate::lexer::Token;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Expr {
    Number(i64),
    Add(Box<Expr>, Box<Expr>),
    Mul(Box<Expr>, Box<Expr>),
}

struct Parser<'a> {
    tokens: &'a [Token],
    pos: usize,
}

pub fn parse(tokens: &[Token]) -> Result<Expr, String> {
    let mut parser = Parser { tokens, pos: 0 };
    let expr = parser.expr()?;
    if parser.pos != tokens.len() {
        return Err("trailing tokens".into());
    }
    Ok(expr)
}

impl<'a> Parser<'a> {
    fn peek(&self) -> Option<&'a Token> { self.tokens.get(self.pos) }
    fn bump(&mut self) -> Option<&'a Token> {
        let token = self.tokens.get(self.pos);
        self.pos += usize::from(token.is_some());
        token
    }
    fn expr(&mut self) -> Result<Expr, String> {
        let mut left = self.term()?;
        while matches!(self.peek(), Some(Token::Plus)) {
            self.bump();
            left = Expr::Add(Box::new(left), Box::new(self.term()?));
        }
        Ok(left)
    }
    fn term(&mut self) -> Result<Expr, String> {
        let mut left = self.factor()?;
        while matches!(self.peek(), Some(Token::Star)) {
            self.bump();
            left = Expr::Mul(Box::new(left), Box::new(self.factor()?));
        }
        Ok(left)
    }
    fn factor(&mut self) -> Result<Expr, String> {
        match self.bump() {
            Some(Token::Number(value)) => Ok(Expr::Number(*value)),
            Some(Token::LParen) => {
                let expr = self.expr()?;
                match self.bump() {
                    Some(Token::RParen) => Ok(expr),
                    _ => Err("expected closing parenthesis".into()),
                }
            }
            _ => Err("expected number or parenthesis".into()),
        }
    }
}
`)
  files.set('src/eval.rs', `use crate::parser::Expr;

pub fn eval(expr: &Expr) -> i64 {
    match expr {
        Expr::Number(value) => *value,
        Expr::Add(left, right) => eval(left) + eval(right),
        Expr::Mul(left, right) => eval(left) * eval(right),
    }
}
`)
  files.set('src/main.rs', `use aurora_mini_compiler::compile_and_run;

fn main() {
    let source = std::env::args().nth(1).unwrap_or_else(|| "1+2*3".to_string());
    match compile_and_run(&source) {
        Ok(value) => println!("{value}"),
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(1);
        }
    }
}
`)
  files.set('tests/language.rs', `use aurora_mini_compiler::{compile_and_run, lex, parse, Token};

#[test]
fn lexer_recognizes_numbers_and_operators() {
    assert_eq!(lex("12 + 3").unwrap(), vec![Token::Number(12), Token::Plus, Token::Number(3)]);
}

#[test]
fn parser_rejects_trailing_tokens() {
    let tokens = vec![Token::Number(1), Token::Number(2)];
    assert!(parse(&tokens).is_err());
}

#[test]
fn precedence_and_parentheses_are_executed() {
    assert_eq!(compile_and_run("1 + 2 * 3").unwrap(), 7);
    assert_eq!(compile_and_run("(2 + 3) * 4").unwrap(), 20);
}
`)
  files.set('README.md', '# Aurora mini compiler proof\n\nExpression compiler/interpreter for integer addition, multiplication and parentheses.\n')
  return files
}

async function writeProject(root: string, files: CodeFile[]) {
  for (const file of files) {
    const target = join(root, file.name)
    await mkdir(dirname(target), { recursive: true })
    await writeFile(target, file.content, 'utf8')
  }
}

describe('codeExtremeCompilerProof', () => {
  test('executor WS3 genere un mini-compilateur Rust qui compile et execute un programme fige', async () => {
    const files = compilerFiles()
    const plan = JSON.stringify({
      schemaVersion: CODE_ARCHITECTURE_PLAN_SCHEMA_VERSION,
      projectType: 'compiler',
      summary: 'Mini compilateur/interpreteur Rust pour expressions arithmetiques avec lexer, parser, AST, eval et tests.',
      stack: {
        runtime: 'rust',
        packageManager: 'cargo',
        languages: ['Rust'],
        frameworks: ['cargo'],
        dependencies: [],
        scripts: [
          { name: 'build', command: 'cargo build', purpose: 'compile' },
          { name: 'test', command: 'cargo test', purpose: 'acceptance' },
        ],
      },
      files: [...files.keys()].map((path, index) => ({
        path,
        role: index === 0 ? 'manifest' : 'compiler source',
        language: languageForPath(path),
        required: true,
        imports: [],
        exports: [],
        notes: [],
      })),
      dataFlow: ['source string -> lexer -> parser AST -> eval -> integer result'],
      execution: {
        install: [],
        dev: ['cargo run -- "1+2*3"'],
        build: ['cargo build'],
        test: ['cargo test'],
        preview: 'console',
      },
      generationOrder: [...files.keys()],
      validation: ['cargo test vert', 'cargo run execute une expression figee'],
      risks: [{ risk: 'precedence invalide', mitigation: 'tests de priorite multiplication et parentheses' }],
      design: { palette: [], typography: [], ux: ['console'], responsive: [] },
    })
    const queue = buildGenerationQueueFromArchitecturePlan(plan)
    assert.ok(queue)

    const result = await executeCodeGenerationQueue({
      queue,
      nextMeta: nextMetaFactory(),
      produceActions: async ({ item }) => [{
        kind: 'write_file',
        path: item.path,
        content: files.get(item.path)!,
        language: languageForPath(item.path),
      }],
    })
    assert.equal(result.ok, true)
    assert.equal(result.files.length, files.size)

    const root = await mkdtemp(join(tmpdir(), 'aurora-ws6-compiler-'))
    try {
      await writeProject(root, result.files)
      execFileSync('cargo', ['test', '--quiet'], { cwd: root, stdio: 'pipe' })
      const output = execFileSync('cargo', ['run', '--quiet', '--', '2+3*4'], { cwd: root, encoding: 'utf8' })
      assert.equal(output.trim(), '14')
    } finally {
      await rm(root, { recursive: true, force: true })
    }
  })
})
