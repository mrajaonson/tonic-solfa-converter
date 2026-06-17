package org.solfadoc.format

import com.intellij.openapi.command.WriteCommandAction
import com.intellij.openapi.util.TextRange
import com.intellij.psi.PsiDocumentManager
import com.intellij.psi.PsiFile
import com.intellij.psi.codeStyle.ExternalFormatProcessor
import org.solfadoc.psi.SolfaFile

class SolfaExternalFormatProcessor : ExternalFormatProcessor {

    override fun getId(): String = "solfadoc"

    override fun activeForFile(source: PsiFile): Boolean = source is SolfaFile

    override fun format(
        source: PsiFile,
        range: TextRange,
        canChangeWhiteSpacesOnly: Boolean,
        keepLineBreaks: Boolean,
        enableBulkUpdate: Boolean,
        cursorOffset: Int
    ): TextRange? {
        val document = PsiDocumentManager.getInstance(source.project).getDocument(source) ?: return null
        val original = document.text
        val formatted = formatSolfaDocument(original)
        if (formatted == original) return range
        WriteCommandAction.runWriteCommandAction(source.project) {
            document.setText(formatted)
        }
        return TextRange(0, formatted.length)
    }

    override fun indent(source: PsiFile, lineStartOffset: Int): String? = null
}
