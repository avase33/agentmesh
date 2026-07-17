//! A tiny, safe arithmetic/logic DSL evaluator.
//!
//! Python agents frequently want to "run some code" to compute a value. Handing
//! arbitrary code to an interpreter is a security nightmare, so instead the
//! executor exposes this bounded expression language: numbers, variables, the
//! usual arithmetic (`+ - * / %`), comparisons, boolean `and`/`or`/`not`, and
//! parentheses. There is no I/O, no loops, no function calls — so it cannot be
//! abused, and it evaluates in microseconds.

use std::collections::HashMap;

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Value {
    Num(f64),
    Bool(bool),
}

impl Value {
    pub fn as_f64(self) -> f64 {
        match self {
            Value::Num(n) => n,
            Value::Bool(b) => {
                if b {
                    1.0
                } else {
                    0.0
                }
            }
        }
    }
}

pub fn eval(expr: &str, vars: &HashMap<String, f64>) -> Result<Value, String> {
    if expr.len() > 4096 {
        return Err("expression too long".into());
    }
    let tokens = lex(expr)?;
    let mut p = Parser { tokens, pos: 0, vars };
    let v = p.parse_or()?;
    if p.pos != p.tokens.len() {
        return Err(format!("unexpected token at {}", p.pos));
    }
    Ok(v)
}

#[derive(Debug, Clone, PartialEq)]
enum Tok {
    Num(f64),
    Ident(String),
    Op(String),
    LParen,
    RParen,
}

fn lex(s: &str) -> Result<Vec<Tok>, String> {
    let mut out = Vec::new();
    let chars: Vec<char> = s.chars().collect();
    let mut i = 0;
    while i < chars.len() {
        let c = chars[i];
        if c.is_whitespace() {
            i += 1;
        } else if c.is_ascii_digit() || (c == '.' && i + 1 < chars.len() && chars[i + 1].is_ascii_digit()) {
            let start = i;
            while i < chars.len() && (chars[i].is_ascii_digit() || chars[i] == '.') {
                i += 1;
            }
            let num: f64 = chars[start..i]
                .iter()
                .collect::<String>()
                .parse()
                .map_err(|_| "bad number".to_string())?;
            out.push(Tok::Num(num));
        } else if c.is_alphabetic() || c == '_' {
            let start = i;
            while i < chars.len() && (chars[i].is_alphanumeric() || chars[i] == '_') {
                i += 1;
            }
            out.push(Tok::Ident(chars[start..i].iter().collect()));
        } else if c == '(' {
            out.push(Tok::LParen);
            i += 1;
        } else if c == ')' {
            out.push(Tok::RParen);
            i += 1;
        } else {
            // multi-char operators first
            let two: String = chars[i..(i + 2).min(chars.len())].iter().collect();
            if ["==", "!=", ">=", "<="].contains(&two.as_str()) {
                out.push(Tok::Op(two));
                i += 2;
            } else if "+-*/%<>".contains(c) {
                out.push(Tok::Op(c.to_string()));
                i += 1;
            } else {
                return Err(format!("unexpected char '{}'", c));
            }
        }
    }
    Ok(out)
}

struct Parser<'a> {
    tokens: Vec<Tok>,
    pos: usize,
    vars: &'a HashMap<String, f64>,
}

impl<'a> Parser<'a> {
    fn peek(&self) -> Option<&Tok> {
        self.tokens.get(self.pos)
    }

    fn eat_op(&mut self, want: &[&str]) -> Option<String> {
        if let Some(Tok::Op(o)) = self.peek() {
            if want.contains(&o.as_str()) {
                let o = o.clone();
                self.pos += 1;
                return Some(o);
            }
        }
        None
    }

    fn eat_ident(&mut self, want: &str) -> bool {
        if let Some(Tok::Ident(id)) = self.peek() {
            if id == want {
                self.pos += 1;
                return true;
            }
        }
        false
    }

    // or := and ("or" and)*
    fn parse_or(&mut self) -> Result<Value, String> {
        let mut left = self.parse_and()?;
        while self.eat_ident("or") {
            let right = self.parse_and()?;
            left = Value::Bool(truthy(left) || truthy(right));
        }
        Ok(left)
    }

    fn parse_and(&mut self) -> Result<Value, String> {
        let mut left = self.parse_cmp()?;
        while self.eat_ident("and") {
            let right = self.parse_cmp()?;
            left = Value::Bool(truthy(left) && truthy(right));
        }
        Ok(left)
    }

    fn parse_cmp(&mut self) -> Result<Value, String> {
        let left = self.parse_add()?;
        if let Some(op) = self.eat_op(&["==", "!=", ">", "<", ">=", "<="]) {
            let right = self.parse_add()?;
            let (a, b) = (left.as_f64(), right.as_f64());
            let r = match op.as_str() {
                "==" => a == b,
                "!=" => a != b,
                ">" => a > b,
                "<" => a < b,
                ">=" => a >= b,
                "<=" => a <= b,
                _ => unreachable!(),
            };
            return Ok(Value::Bool(r));
        }
        Ok(left)
    }

    fn parse_add(&mut self) -> Result<Value, String> {
        let mut left = self.parse_mul()?;
        while let Some(op) = self.eat_op(&["+", "-"]) {
            let right = self.parse_mul()?;
            let (a, b) = (left.as_f64(), right.as_f64());
            left = Value::Num(if op == "+" { a + b } else { a - b });
        }
        Ok(left)
    }

    fn parse_mul(&mut self) -> Result<Value, String> {
        let mut left = self.parse_unary()?;
        while let Some(op) = self.eat_op(&["*", "/", "%"]) {
            let right = self.parse_unary()?;
            let (a, b) = (left.as_f64(), right.as_f64());
            left = Value::Num(match op.as_str() {
                "*" => a * b,
                "/" => {
                    if b == 0.0 {
                        return Err("division by zero".into());
                    }
                    a / b
                }
                "%" => {
                    if b == 0.0 {
                        return Err("modulo by zero".into());
                    }
                    a % b
                }
                _ => unreachable!(),
            });
        }
        Ok(left)
    }

    fn parse_unary(&mut self) -> Result<Value, String> {
        if self.eat_ident("not") {
            let v = self.parse_unary()?;
            return Ok(Value::Bool(!truthy(v)));
        }
        if let Some(op) = self.eat_op(&["-", "+"]) {
            let v = self.parse_unary()?;
            return Ok(Value::Num(if op == "-" { -v.as_f64() } else { v.as_f64() }));
        }
        self.parse_atom()
    }

    fn parse_atom(&mut self) -> Result<Value, String> {
        match self.peek().cloned() {
            Some(Tok::Num(n)) => {
                self.pos += 1;
                Ok(Value::Num(n))
            }
            Some(Tok::Ident(id)) => {
                self.pos += 1;
                match id.as_str() {
                    "true" => Ok(Value::Bool(true)),
                    "false" => Ok(Value::Bool(false)),
                    _ => self
                        .vars
                        .get(&id)
                        .copied()
                        .map(Value::Num)
                        .ok_or_else(|| format!("unknown variable '{}'", id)),
                }
            }
            Some(Tok::LParen) => {
                self.pos += 1;
                let v = self.parse_or()?;
                if self.peek() == Some(&Tok::RParen) {
                    self.pos += 1;
                    Ok(v)
                } else {
                    Err("expected ')'".into())
                }
            }
            other => Err(format!("unexpected token: {:?}", other)),
        }
    }
}

fn truthy(v: Value) -> bool {
    match v {
        Value::Bool(b) => b,
        Value::Num(n) => n != 0.0,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ev(s: &str) -> Value {
        eval(s, &HashMap::new()).unwrap()
    }

    #[test]
    fn arithmetic_precedence() {
        assert_eq!(ev("2 + 3 * 4").as_f64(), 14.0);
        assert_eq!(ev("(2 + 3) * 4").as_f64(), 20.0);
        assert_eq!(ev("10 % 3").as_f64(), 1.0);
        assert_eq!(ev("-5 + 2").as_f64(), -3.0);
    }

    #[test]
    fn variables() {
        let mut vars = HashMap::new();
        vars.insert("tokens".to_string(), 1000.0);
        assert!((eval("tokens * 0.000002", &vars).unwrap().as_f64() - 0.002).abs() < 1e-9);
    }

    #[test]
    fn logic_and_comparison() {
        assert_eq!(ev("3 > 2 and 1 < 2"), Value::Bool(true));
        assert_eq!(ev("not (5 == 5)"), Value::Bool(false));
        assert_eq!(ev("2 == 2 or 1 == 2"), Value::Bool(true));
    }

    #[test]
    fn rejects_unknown_and_bad() {
        assert!(eval("open('/etc/passwd')", &HashMap::new()).is_err());
        assert!(eval("1 / 0", &HashMap::new()).is_err());
        assert!(eval("x + 1", &HashMap::new()).is_err());
    }
}
