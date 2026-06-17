package org.solfadoc.format

private val MUSIC_LINE_RE = Regex("""^\s*(?:(?:PR|PL|[SATB]\d*)[ \t]+)?\|""")
private val VOICE_LABEL_RE = Regex("""^\s*(?:(PR|PL|[SATB]\d*)[ \t]+)?(\|[\s\S]*)""")
private val SEP_RE = Regex("""\|\||[|!:]""")
private val HEADER_RE = Regex("""^\w[\w\s]*:\s""")
private val VERSE_PREFIX_RE = Regex("""^(\d+|R)[ \t]""")

private data class MusicLine(
    val label: String,
    val measures: List<Pair<String, String>>,  // (sep, content)
    val trailingSep: String
)

private fun splitOnSeps(text: String): List<String> {
    val result = mutableListOf<String>()
    var last = 0
    for (match in SEP_RE.findAll(text)) {
        result.add(text.substring(last, match.range.first))
        result.add(match.value)
        last = match.range.last + 1
    }
    result.add(text.substring(last))
    return result
}

private fun parseLine(line: String): MusicLine? {
    val m = VOICE_LABEL_RE.find(line) ?: return null
    val label = m.groupValues[1]
    val rest = m.groupValues[2]  // starts with |

    val parts = splitOnSeps(rest)
    // parts: [pre, sep, content, sep, content, ..., trailing]
    // pre is always "" (rest starts with |), then sep at index 1, content at index 2, etc.
    val pairs = mutableListOf<Pair<String, String>>()
    var i = 1
    while (i < parts.size) {
        val sep = parts[i]
        val content = if (i + 1 < parts.size) parts[i + 1].trim() else ""
        pairs.add(sep to content)
        i += 2
    }
    if (pairs.isEmpty()) return null

    var trailingSep = ""
    val measures = mutableListOf<Pair<String, String>>()
    for (j in pairs.indices) {
        val (sep, content) = pairs[j]
        if (j == pairs.size - 1 && content.isEmpty()) {
            trailingSep = sep
        } else {
            measures.add(sep to content)
        }
    }
    return MusicLine(label, measures, trailingSep)
}

private fun formatLines(lines: List<MusicLine>, prefixLen: Int, colWidths: List<Int>): List<String> {
    return lines.map { p ->
        val sb = StringBuilder()
        sb.append(p.label.padEnd(prefixLen))
        for (i in p.measures.indices) {
            val (sep, content) = p.measures[i]
            val width = if (i < colWidths.size) colWidths[i] else content.length
            sb.append(' ').append(sep).append(' ').append(content.padEnd(width))
        }
        if (p.trailingSep.isNotEmpty()) sb.append(' ').append(p.trailingSep)
        sb.toString().trimEnd()
    }
}

private fun isLyricsLine(line: String): Boolean {
    if (line.isBlank()) return false
    val s = line.trimStart()
    if (s.startsWith("//") || s.startsWith("#") || s.startsWith("[") || s.startsWith(":")) return false
    if (HEADER_RE.containsMatchIn(s)) return false
    if (VERSE_PREFIX_RE.containsMatchIn(s)) return false
    return true
}

fun formatSolfaDocument(text: String): String {
    val eol = if (text.contains("\r\n")) "\r\n" else "\n"
    val rawLines = text.split(Regex("""\r?\n"""))

    data class BlockInfo(val start: Int, val parsed: List<MusicLine>)
    val blocks = mutableListOf<BlockInfo>()
    val bLines = mutableListOf<String>()
    var bStart = -1

    for (i in 0..rawLines.size) {
        val line = if (i < rawLines.size) rawLines[i] else ""
        if (i < rawLines.size && MUSIC_LINE_RE.containsMatchIn(line)) {
            if (bStart == -1) bStart = i
            bLines.add(line)
        } else if (bStart != -1) {
            val parsed = bLines.map { parseLine(it) }
            if (parsed.none { it == null }) {
                blocks.add(BlockInfo(bStart, parsed.filterNotNull()))
            }
            bLines.clear()
            bStart = -1
        }
    }

    if (blocks.isEmpty()) return text

    val gPrefixLen = blocks.flatMap { b -> b.parsed.map { it.label.length } }.maxOrNull() ?: 0
    val gNumCols = blocks.maxOf { b -> b.parsed.maxOfOrNull { it.measures.size } ?: 0 }
    val gColWidths = List(gNumCols) { c ->
        blocks.flatMap { b -> b.parsed.map { it.measures.getOrNull(c)?.second?.length ?: 0 } }.maxOrNull() ?: 0
    }

    val lyricsIndent = " ".repeat(gPrefixLen + 3)
    val formattedBlocks = blocks.map { b -> formatLines(b.parsed, gPrefixLen, gColWidths) }

    val lineOwner = mutableMapOf<Int, Pair<Int, Int>>()
    blocks.forEachIndexed { bi, b -> b.parsed.forEachIndexed { li, _ -> lineOwner[b.start + li] = bi to li } }

    val result = mutableListOf<String>()
    var inNotesSection = false
    for ((i, line) in rawLines.withIndex()) {
        if (line.trimStart().lowercase().startsWith("[notes]")) inNotesSection = true
        val owner = lineOwner[i]
        result.add(when {
            owner != null -> formattedBlocks[owner.first][owner.second]
            !inNotesSection && isLyricsLine(line) -> lyricsIndent + line.trimStart()
            else -> line
        })
    }
    return result.joinToString(eol)
}
