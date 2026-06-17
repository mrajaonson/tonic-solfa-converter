package org.solfadoc.highlight

import com.intellij.lexer.Lexer
import com.intellij.openapi.editor.DefaultLanguageHighlighterColors
import com.intellij.openapi.editor.HighlighterColors
import com.intellij.openapi.editor.colors.TextAttributesKey
import com.intellij.openapi.fileTypes.SyntaxHighlighterBase
import com.intellij.psi.tree.IElementType
import org.solfadoc.lexer.SolfaLexerAdapter
import org.solfadoc.lexer.SolfaTokenTypes

class SolfaSyntaxHighlighter : SyntaxHighlighterBase() {

    companion object {
        // Tokens with theme fallbacks - intentionally inheriting from the active color scheme
        val COMMENT           = TextAttributesKey.createTextAttributesKey("SOLFA_COMMENT",        DefaultLanguageHighlighterColors.LINE_COMMENT)
        val HEADER_VALUE      = TextAttributesKey.createTextAttributesKey("SOLFA_HEADER_VALUE",   DefaultLanguageHighlighterColors.STRING)
        val LYRICS_TEXT       = TextAttributesKey.createTextAttributesKey("SOLFA_LYRICS_TEXT",    DefaultLanguageHighlighterColors.STRING)
        val BAD_CHAR          = TextAttributesKey.createTextAttributesKey("SOLFA_BAD_CHARACTER",  HighlighterColors.BAD_CHARACTER)

        // All other tokens - no fallback; colors come exclusively from additionalTextAttributes XML.
        // Without a fallback, IntelliJ renders unset tokens in the default editor text color,
        // which is the correct baseline for notes and plain text tokens.
        val HEADER_KEY        = TextAttributesKey.createTextAttributesKey("SOLFA_HEADER_KEY")
        val HEADER_DELIM      = TextAttributesKey.createTextAttributesKey("SOLFA_HEADER_DELIM")
        val VOICE_LABEL       = TextAttributesKey.createTextAttributesKey("SOLFA_VOICE_LABEL")
        val NOTE              = TextAttributesKey.createTextAttributesKey("SOLFA_NOTE")
        val CHROMATIC_NOTE    = TextAttributesKey.createTextAttributesKey("SOLFA_CHROMATIC_NOTE")
        val REST              = TextAttributesKey.createTextAttributesKey("SOLFA_REST")
        val HOLD              = TextAttributesKey.createTextAttributesKey("SOLFA_HOLD")
        val BARLINE           = TextAttributesKey.createTextAttributesKey("SOLFA_BARLINE")
        val BEAT_SEP          = TextAttributesKey.createTextAttributesKey("SOLFA_BEAT_SEP")
        val SUBBEAT_SEP       = TextAttributesKey.createTextAttributesKey("SOLFA_SUBBEAT_SEP")
        val OCTAVE            = TextAttributesKey.createTextAttributesKey("SOLFA_OCTAVE")
        val DYNAMICS          = TextAttributesKey.createTextAttributesKey("SOLFA_DYNAMICS")
        val NAVIGATION        = TextAttributesKey.createTextAttributesKey("SOLFA_NAVIGATION")
        val CHORD_BRACKET     = TextAttributesKey.createTextAttributesKey("SOLFA_CHORD_BRACKET")
        val LYRICS_PREFIX     = TextAttributesKey.createTextAttributesKey("SOLFA_LYRICS_PREFIX")
        val LYRICS_JOIN       = TextAttributesKey.createTextAttributesKey("SOLFA_LYRICS_JOIN")
        val LYRICS_HYPHEN     = TextAttributesKey.createTextAttributesKey("SOLFA_LYRICS_HYPHEN")
        val LYRICS_REST_SKIP  = TextAttributesKey.createTextAttributesKey("SOLFA_LYRICS_REST_SKIP")
        val LYRICS_MUTE_DELIM = TextAttributesKey.createTextAttributesKey("SOLFA_LYRICS_MUTE_DELIM")
        val MODULATION_SEP    = TextAttributesKey.createTextAttributesKey("SOLFA_MODULATION_SEP")
        val NOTES_SECTION_MARKER = TextAttributesKey.createTextAttributesKey("SOLFA_NOTES_SECTION_MARKER")
        val NOTES_SECTION_TEXT   = TextAttributesKey.createTextAttributesKey("SOLFA_NOTES_SECTION_TEXT")
    }

    override fun getHighlightingLexer(): Lexer = SolfaLexerAdapter()

    override fun getTokenHighlights(tokenType: IElementType?): Array<TextAttributesKey> {
        return when (tokenType) {
            SolfaTokenTypes.COMMENT -> arrayOf(COMMENT)
            SolfaTokenTypes.HEADER_PREFIX, SolfaTokenTypes.HEADER_SUFFIX -> arrayOf(HEADER_DELIM)
            SolfaTokenTypes.HEADER_KEY -> arrayOf(HEADER_KEY)
            SolfaTokenTypes.HEADER_VALUE -> arrayOf(HEADER_VALUE)
            SolfaTokenTypes.VOICE_LABEL -> arrayOf(VOICE_LABEL)
            SolfaTokenTypes.NOTE -> arrayOf(NOTE)
            SolfaTokenTypes.CHROMATIC_NOTE -> arrayOf(CHROMATIC_NOTE)
            SolfaTokenTypes.REST -> arrayOf(REST)
            SolfaTokenTypes.HOLD -> arrayOf(HOLD)
            SolfaTokenTypes.BARLINE, SolfaTokenTypes.DOUBLE_BARLINE, SolfaTokenTypes.SOFT_BARLINE -> arrayOf(BARLINE)
            SolfaTokenTypes.BEAT_SEPARATOR -> arrayOf(BEAT_SEP)
            SolfaTokenTypes.SUBBEAT_SEPARATOR -> arrayOf(SUBBEAT_SEP)
            SolfaTokenTypes.OCTAVE_UP, SolfaTokenTypes.OCTAVE_DOWN -> arrayOf(OCTAVE)
            SolfaTokenTypes.STACCATO, SolfaTokenTypes.MELISMA -> arrayOf(DYNAMICS)
            SolfaTokenTypes.DYNAMICS -> arrayOf(DYNAMICS)
            SolfaTokenTypes.NAVIGATION -> arrayOf(NAVIGATION)
            SolfaTokenTypes.CHORD_OPEN, SolfaTokenTypes.CHORD_CLOSE -> arrayOf(CHORD_BRACKET)
            SolfaTokenTypes.LYRICS_PREFIX -> arrayOf(LYRICS_PREFIX)
            SolfaTokenTypes.LYRICS_TEXT -> arrayOf(LYRICS_TEXT)
            SolfaTokenTypes.LYRICS_JOIN -> arrayOf(LYRICS_JOIN)
            SolfaTokenTypes.LYRICS_HYPHEN -> arrayOf(LYRICS_HYPHEN)
            SolfaTokenTypes.LYRICS_REST_SKIP -> arrayOf(LYRICS_REST_SKIP)
            SolfaTokenTypes.LYRICS_MUTE_DELIM -> arrayOf(LYRICS_MUTE_DELIM)
            SolfaTokenTypes.MODULATION_SEP -> arrayOf(MODULATION_SEP)
            SolfaTokenTypes.NOTES_SECTION_MARKER -> arrayOf(NOTES_SECTION_MARKER)
            SolfaTokenTypes.NOTES_SECTION_TEXT -> arrayOf(NOTES_SECTION_TEXT)
            SolfaTokenTypes.BAD_CHARACTER -> arrayOf(BAD_CHAR)
            else -> emptyArray()
        }
    }
}
