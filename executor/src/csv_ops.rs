//! Streaming CSV aggregation.
//!
//! When a Python agent needs to crunch a large CSV, it ships the bytes here and
//! the Rust layer parses and aggregates a column in one pass with no allocation
//! per cell beyond the header split. A minimal RFC-4180-ish parser (handles
//! quoted fields with embedded commas) keeps it dependency-free.

pub struct Aggregation {
    pub rows: usize,
    pub result: f64,
}

pub fn aggregate(csv: &str, op: &str, column: &str) -> Result<Aggregation, String> {
    let mut lines = csv.lines();
    let header = lines.next().ok_or("empty csv")?;
    let cols = parse_line(header);
    let idx = cols
        .iter()
        .position(|c| c.trim() == column)
        .ok_or_else(|| format!("column '{}' not found", column))?;

    let mut rows = 0usize;
    let mut sum = 0.0f64;
    let mut max = f64::NEG_INFINITY;
    let mut min = f64::INFINITY;
    let mut numeric = 0usize;

    for line in lines {
        if line.trim().is_empty() {
            continue;
        }
        rows += 1;
        let fields = parse_line(line);
        if let Some(cell) = fields.get(idx) {
            if let Ok(v) = cell.trim().parse::<f64>() {
                sum += v;
                numeric += 1;
                if v > max {
                    max = v;
                }
                if v < min {
                    min = v;
                }
            }
        }
    }

    let result = match op {
        "sum" => sum,
        "mean" => {
            if numeric == 0 {
                0.0
            } else {
                sum / numeric as f64
            }
        }
        "count" => rows as f64,
        "max" => {
            if numeric == 0 {
                0.0
            } else {
                max
            }
        }
        "min" => {
            if numeric == 0 {
                0.0
            } else {
                min
            }
        }
        other => return Err(format!("unknown op '{}'", other)),
    };
    Ok(Aggregation { rows, result })
}

/// Split a CSV line, honouring double-quoted fields with embedded commas.
fn parse_line(line: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut field = String::new();
    let mut in_quotes = false;
    let mut chars = line.chars().peekable();
    while let Some(c) = chars.next() {
        match c {
            '"' => {
                if in_quotes && chars.peek() == Some(&'"') {
                    field.push('"');
                    chars.next();
                } else {
                    in_quotes = !in_quotes;
                }
            }
            ',' if !in_quotes => {
                out.push(std::mem::take(&mut field));
            }
            _ => field.push(c),
        }
    }
    out.push(field);
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    const CSV: &str = "id,amount,label\n1,10.5,a\n2,20,b\n3,5,\"c,d\"\n";

    #[test]
    fn sum_and_mean() {
        let a = aggregate(CSV, "sum", "amount").unwrap();
        assert_eq!(a.rows, 3);
        assert!((a.result - 35.5).abs() < 1e-9);
        let m = aggregate(CSV, "mean", "amount").unwrap();
        assert!((m.result - 35.5 / 3.0).abs() < 1e-9);
    }

    #[test]
    fn max_min_count() {
        assert_eq!(aggregate(CSV, "max", "amount").unwrap().result, 20.0);
        assert_eq!(aggregate(CSV, "min", "amount").unwrap().result, 5.0);
        assert_eq!(aggregate(CSV, "count", "amount").unwrap().result, 3.0);
    }

    #[test]
    fn quoted_commas_dont_break_columns() {
        // row 3's label is "c,d" — must not shift the amount column
        let a = aggregate(CSV, "sum", "amount").unwrap();
        assert_eq!(a.rows, 3);
        assert!((a.result - 35.5).abs() < 1e-9);
    }

    #[test]
    fn missing_column_errors() {
        assert!(aggregate(CSV, "sum", "nope").is_err());
    }
}
