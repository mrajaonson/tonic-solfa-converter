package org.solfadoc.format

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class SolfaFormatterTest {

    // Strip the leading newline from indented triple-quoted strings.
    private fun doc(s: String) = s.removePrefix("\n")

    @Test fun `no-op when no music lines`() {
        val input = "title: My Song\nkey: C major\n"
        assertEquals(input, formatSolfaDocument(input))
    }

    @Test fun `aligns a labeled block`() {
        assertEquals(
            doc("""
S | d : m ! s  |
A | d : d ! t, |"""),
            formatSolfaDocument(doc("""
S | d : m ! s |
A | d : d ! t, |"""))
        )
    }

    @Test fun `aligns voice labels PR and PL`() {
        assertEquals(
            doc("""
PR | d : m |
PL | l : s |"""),
            formatSolfaDocument(doc("""
PR | d : m |
PL | l : s |"""))
        )
    }

    @Test fun `unlabeled block — first barline with single leading space`() {
        assertEquals(
            doc("""
 | d : m |
 | l : s |"""),
            formatSolfaDocument(doc("""
   | d : m |
   | l : s |"""))
        )
    }

    @Test fun `global column widths — narrower block padded to match wider block`() {
        assertEquals(
            doc("""
S | x    |

S | long |"""),
            formatSolfaDocument(doc("""
S | x |

S | long |"""))
        )
    }

    @Test fun `global prefix — unlabeled block indented to match labeled block`() {
        assertEquals(
            doc("""
S | d : m |

  | l : s |"""),
            formatSolfaDocument(doc("""
S | d : m |

  | l : s |"""))
        )
    }

    @Test fun `double barline is treated as a separator`() {
        assertEquals("S | d || m |", formatSolfaDocument("S | d || m |"))
    }

    @Test fun `trailing barline preserved`() {
        assertEquals("S | d : m |", formatSolfaDocument("S | d : m |"))
    }

    @Test fun `lyrics indented to first-measure column`() {
        assertEquals(
            doc("""
S | d : m |
A | l : s |
    sing ing words"""),
            formatSolfaDocument(doc("""
S | d : m |
A | l : s |
sing ing words"""))
        )
    }

    @Test fun `non-indented lyrics also aligned`() {
        assertEquals(
            doc("""
S | d |
    sing ing"""),
            formatSolfaDocument(doc("""
S | d |
sing ing"""))
        )
    }

    @Test fun `headers (key-value) not treated as lyrics`() {
        val out = formatSolfaDocument(doc("""
title: My Song
S | d |
composer: Someone"""))
        assertTrue(out.contains("title: My Song"), "header before block unchanged")
        assertTrue(out.contains("composer: Someone"), "header after block unchanged")
    }

    @Test fun `comments and section markers not treated as lyrics`() {
        val out = formatSolfaDocument(doc("""
S | d |
// a comment
[section]"""))
        assertTrue(out.contains("// a comment"))
        assertTrue(out.contains("[section]"))
    }

    @Test fun `verse and refrain prefixes not treated as lyrics`() {
        val out = formatSolfaDocument(doc("""
S | d |
1 first verse
R refrain line"""))
        assertTrue(out.contains("1 first verse"))
        assertTrue(out.contains("R refrain line"))
    }

    @Test fun `notes section content not indented`() {
        assertEquals(
            doc("""
S | d |
[notes]
free text here
more text"""),
            formatSolfaDocument(doc("""
S | d |
[notes]
free text here
more text"""))
        )
    }

    @Test fun `notes detection is case-insensitive`() {
        val out = formatSolfaDocument(doc("""
S | d |
[Notes]
free text"""))
        assertTrue(out.contains("\nfree text"))
    }

    @Test fun `CRLF line endings preserved`() {
        val input = "S | d : m |\r\nA | l : s |\r\n"
        assertTrue(formatSolfaDocument(input).contains("\r\n"))
    }

    @Test fun `idempotent — formatting twice gives the same result`() {
        val input = doc("""
S  | d : m ! s |
A  | d : d ! t, |
sing ing
// comment
[notes]
free text""")
        val once = formatSolfaDocument(input)
        assertEquals(once, formatSolfaDocument(once))
    }
}
