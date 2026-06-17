import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { formatDocument } from '../formatter';

// Strip the leading newline from indented template literals.
const doc = (s: string) => s.replace(/^\n/, '');

test('no-op when no music lines', () => {
    const input = 'title: My Song\nkey: C major\n';
    assert.equal(formatDocument(input), input);
});

test('aligns a labeled block', () => {
    assert.equal(
        formatDocument(doc(`
S | d : m ! s |
A | d : d ! t, |`)),
        doc(`
S | d : m ! s  |
A | d : d ! t, |`)
    );
});

test('aligns voice labels PR and PL', () => {
    assert.equal(
        formatDocument(doc(`
PR | d : m |
PL | l : s |`)),
        doc(`
PR | d : m |
PL | l : s |`)
    );
});

test('unlabeled block — first barline lines up with single leading space', () => {
    assert.equal(
        formatDocument(doc(`
   | d : m |
   | l : s |`)),
        doc(`
 | d : m |
 | l : s |`)
    );
});

test('global column widths: narrower block padded to match wider block', () => {
    assert.equal(
        formatDocument(doc(`
S | x |

S | long |`)),
        doc(`
S | x    |

S | long |`)
    );
});

test('global prefix: unlabeled block indented to match labeled block', () => {
    assert.equal(
        formatDocument(doc(`
S | d : m |

  | l : s |`)),
        doc(`
S | d : m |

  | l : s |`)
    );
});

test('double barline || is treated as a separator', () => {
    assert.equal(
        formatDocument('S | d || m |'),
        'S | d || m |'
    );
});

test('trailing barline preserved', () => {
    assert.equal(
        formatDocument('S | d : m |'),
        'S | d : m |'
    );
});

test('lyrics indented to first-measure column', () => {
    assert.equal(
        formatDocument(doc(`
S | d : m |
A | l : s |
sing ing words`)),
        doc(`
S | d : m |
A | l : s |
    sing ing words`)
    );
});

test('non-indented lyrics also aligned', () => {
    assert.equal(
        formatDocument(doc(`
S | d |
sing ing`)),
        doc(`
S | d |
    sing ing`)
    );
});

test('headers (key: value) not treated as lyrics', () => {
    const input = doc(`
title: My Song
S | d |
composer: Someone`);
    const out = formatDocument(input);
    assert.ok(out.includes('title: My Song'), 'header before block unchanged');
    assert.ok(out.includes('composer: Someone'), 'header after block unchanged');
});

test('comments and section markers not treated as lyrics', () => {
    const input = doc(`
S | d |
// a comment
[section]`);
    const out = formatDocument(input);
    assert.ok(out.includes('// a comment'));
    assert.ok(out.includes('[section]'));
});

test('verse and refrain prefixes not treated as lyrics', () => {
    const input = doc(`
S | d |
1 first verse
R refrain line`);
    const out = formatDocument(input);
    assert.ok(out.includes('1 first verse'));
    assert.ok(out.includes('R refrain line'));
});

test('[notes] section content not indented', () => {
    assert.equal(
        formatDocument(doc(`
S | d |
[notes]
free text here
more text`)),
        doc(`
S | d |
[notes]
free text here
more text`)
    );
});

test('[notes] detection is case-insensitive', () => {
    const out = formatDocument(doc(`
S | d |
[Notes]
free text`));
    assert.ok(out.includes('\nfree text'));
});

test('CRLF line endings preserved', () => {
    const input = 'S | d : m |\r\nA | l : s |\r\n';
    assert.ok(formatDocument(input).includes('\r\n'));
});

test('idempotent — formatting twice gives the same result', () => {
    const input = doc(`
S  | d : m ! s |
A  | d : d ! t, |
sing ing
// comment
[notes]
free text`);
    const once = formatDocument(input);
    assert.equal(formatDocument(once), once);
});
