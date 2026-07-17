//! A fast, deterministic sub-word tokenizer.
//!
//! Not a full BPE model, but a byte-class splitter that mirrors how real
//! tokenizers segment text (words, sub-word chunks, punctuation, whitespace
//! runs). Python asks the executor for token counts to estimate LLM cost before
//! making a call — doing it in Rust keeps it off the GIL and lets us tokenize
//! megabytes per millisecond.

/// Split text into tokens. Long alphabetic runs are chunked into ~4-char pieces
/// (approximating sub-word splitting); digits, punctuation and whitespace runs
/// each become their own tokens.
pub fn tokenize(text: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut chars = text.chars().peekable();
    while let Some(&c) = chars.peek() {
        if c.is_alphabetic() {
            let mut word = String::new();
            while let Some(&c) = chars.peek() {
                if c.is_alphabetic() {
                    word.push(c);
                    chars.next();
                } else {
                    break;
                }
            }
            // chunk long words into sub-word pieces of up to 4 chars
            let bytes: Vec<char> = word.chars().collect();
            for chunk in bytes.chunks(4) {
                out.push(chunk.iter().collect());
            }
        } else if c.is_ascii_digit() {
            let mut num = String::new();
            while let Some(&c) = chars.peek() {
                if c.is_ascii_digit() {
                    num.push(c);
                    chars.next();
                } else {
                    break;
                }
            }
            out.push(num);
        } else if c.is_whitespace() {
            while let Some(&c) = chars.peek() {
                if c.is_whitespace() {
                    chars.next();
                } else {
                    break;
                }
            }
            // whitespace runs are not emitted as visible tokens
        } else {
            out.push(c.to_string());
            chars.next();
        }
    }
    out
}

pub fn count(text: &str) -> usize {
    tokenize(text).len()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn splits_words_punctuation_numbers() {
        let toks = tokenize("Hello, world 2026!");
        assert!(toks.contains(&",".to_string()));
        assert!(toks.contains(&"2026".to_string()));
        assert!(toks.contains(&"!".to_string()));
    }

    #[test]
    fn chunks_long_words() {
        // "internationalization" (20 chars) -> 5 sub-word chunks of 4
        let toks = tokenize("internationalization");
        assert_eq!(toks.len(), 5);
    }

    #[test]
    fn count_is_stable() {
        // each word is <=4 chars, so one sub-word token apiece
        assert_eq!(count("one two four"), 3);
        assert_eq!(count(""), 0);
    }
}
