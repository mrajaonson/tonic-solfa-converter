const MUSIC_LINE_RE = /^(?:\s*)(?:(?:PR|PL|[SATB]\d*)[ \t]+)?\|/;
const SEP_SPLIT_RE = /((?:\|\|)|\||!|:)/;

interface MusicLine {
    label: string;
    measures: Array<{ sep: string; content: string }>;
    trailingSep: string;
}

function parseLine(line: string): MusicLine | null {
    const m = line.match(/^(?:\s*)(?:(PR|PL|[SATB]\d*)[ \t]+)?(\|[\s\S]*)/);
    if (!m) return null;

    const label = m[1] ?? '';
    const rest = m[2];

    const parts = rest.split(SEP_SPLIT_RE);
    const pairs: Array<[string, string]> = [];
    for (let i = 1; i < parts.length; i += 2) {
        const sep = parts[i];
        const content = (i + 1 < parts.length ? parts[i + 1] : '').trim();
        pairs.push([sep, content]);
    }
    if (pairs.length === 0) return null;

    let trailingSep = '';
    const measures: Array<{ sep: string; content: string }> = [];
    for (let i = 0; i < pairs.length; i++) {
        const [sep, content] = pairs[i];
        if (i === pairs.length - 1 && content === '') {
            trailingSep = sep;
        } else {
            measures.push({ sep, content });
        }
    }
    return { label, measures, trailingSep };
}

function formatLines(ps: MusicLine[], prefixLen: number, colWidths: number[]): string[] {
    return ps.map(p => {
        let out = p.label.padEnd(prefixLen);
        for (let i = 0; i < p.measures.length; i++) {
            const { sep, content } = p.measures[i];
            const width = i < colWidths.length ? colWidths[i] : content.length;
            out += ' ' + sep + ' ' + content.padEnd(width);
        }
        if (p.trailingSep) out += ' ' + p.trailingSep;
        return out.trimEnd();
    });
}

function isLyricsLine(line: string): boolean {
    if (!line.trim()) return false;
    const s = line.trimStart();
    if (/^(\/\/|#|\[|:)/.test(s)) return false;
    if (/^\w[\w\s]*:\s/.test(s)) return false;
    if (/^(\d+|R)[ \t]/.test(s)) return false;
    return true;
}

export function formatDocument(text: string): string {
    const eol = text.includes('\r\n') ? '\r\n' : '\n';
    const rawLines = text.split(/\r?\n/);

    type BlockInfo = { start: number; parsed: MusicLine[] };
    const blocks: BlockInfo[] = [];
    let bLines: string[] = [];
    let bStart = -1;

    for (let i = 0; i <= rawLines.length; i++) {
        const line = i < rawLines.length ? rawLines[i] : '';
        if (i < rawLines.length && MUSIC_LINE_RE.test(line)) {
            if (bStart === -1) bStart = i;
            bLines.push(line);
        } else if (bStart !== -1) {
            const parsed = bLines.map(parseLine);
            if (!parsed.some(p => p === null)) {
                blocks.push({ start: bStart, parsed: parsed as MusicLine[] });
            }
            bLines = [];
            bStart = -1;
        }
    }

    if (blocks.length === 0) return text;

    const gPrefixLen = Math.max(0, ...blocks.flatMap(b => b.parsed.map(p => p.label.length)));
    const gNumCols = Math.max(0, ...blocks.map(b => Math.max(0, ...b.parsed.map(p => p.measures.length))));
    const gColWidths = Array.from({ length: gNumCols }, (_, c) =>
        Math.max(0, ...blocks.flatMap(b => b.parsed.map(p => p.measures[c]?.content.length ?? 0)))
    );
    const lyricsIndent = ' '.repeat(gPrefixLen + 3);

    const formattedBlocks = blocks.map(b => formatLines(b.parsed, gPrefixLen, gColWidths));

    const lineOwner = new Map<number, { bi: number; li: number }>();
    blocks.forEach((b, bi) => b.parsed.forEach((_, li) => lineOwner.set(b.start + li, { bi, li })));

    const result: string[] = [];
    let inNotesSection = false;
    for (let i = 0; i < rawLines.length; i++) {
        const line = rawLines[i];
        if (line.trimStart().toLowerCase().startsWith('[notes]')) inNotesSection = true;
        const owner = lineOwner.get(i);
        if (owner) result.push(formattedBlocks[owner.bi][owner.li]);
        else if (!inNotesSection && isLyricsLine(line)) result.push(lyricsIndent + line.trimStart());
        else result.push(line);
    }

    return result.join(eol);
}
