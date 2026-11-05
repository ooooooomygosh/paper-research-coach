"""Localized citation presentation without changing canonical evidence."""
from collections import Counter
from contextvars import ContextVar
from html import escape
import re

SOURCE_LABELS = ContextVar('learning_source_labels', default={})
HAN = re.compile(r'[\u3400-\u9fff]')


def canonical_sources(value, field=''):
    if field == 'sourceLabels':
        return set()
    if isinstance(value, str):
        return {value} if field in {'source', 'locator', 'sourceDetails'} else set()
    if isinstance(value, list):
        return set().union(*(canonical_sources(x, field) for x in value)) if value else set()
    if isinstance(value, dict):
        return set().union(*(canonical_sources(x, 'sourceDetails' if field == 'sourceDetails' else k) for k, x in value.items())) if value else set()
    return set()


def number_signature(value):
    return Counter(int(x) for x in re.findall(r'\d+', value))


def locator_signature(value):
    signatures = {}
    for kind, pattern in {
        'pdf': r'PDF\s*(?:第\s*|(?:pp?\.|pages?)\s*)(\d+)(?:\s*[–—-]\s*(\d+))?',
        'printed': r'(?:原书\s*第\s*|(?:Printed|Original book)\s*(?:pp?\.|pages?)\s*)(\d+)(?:\s*[–—-]\s*(\d+))?',
        'chapter': r'(?:第\s*(\d+)\s*章|Chapter\s+(\d+))',
    }.items():
        values = []
        for match in re.finditer(pattern, value, re.I):
            if kind == 'chapter':
                values.append(int(match[1] or match[2]))
            else:
                values.append((int(match[1]), int(match[2] or match[1])))
        signatures[kind] = Counter(values)
    return signatures


def english_locator_syntax(raw):
    value = re.sub(r'原书\s*第\s*([\d–—\-\s]+)页', r'Printed pp. \1', raw)
    value = re.sub(r'PDF\s*第\s*([\d–—\-\s]+)页', r'PDF pp. \1', value)
    return re.sub(r'第\s*(\d+)\s*章', r'Chapter \1', value)


def source_filenames(raw):
    # Citation components use spaced middle dots. An unspaced middle dot or a
    # space can be part of a real filename, e.g. 埃隆·马斯克 传.pdf.
    output = []
    for part in re.split(r'\s+[·•]\s+|[；;\n]', raw):
        match = re.fullmatch(r'\s*(.+\.(?:pdf|epub|txt|md|html|docx|pptx|rtf))\s*', part, re.I)
        if match:
            output.append(re.sub(r'^(?:来源|Source)\s*[:：]\s*', '', match[1], flags=re.I))
        else:
            output.extend(re.findall(r'[^\s·；;]+\.(?:pdf|epub|txt|md|html|docx|pptx|rtf)\b', part, re.I))
    return sorted(set(output),key=len,reverse=True)


def without_filenames(value, raw):
    for filename in source_filenames(raw):
        value = value.replace(filename, '')
    return value


def validate_labels(data, errors, require_complete=False):
    labels = data.get('sourceLabels', {})
    if not isinstance(labels, dict):
        errors.append('sourceLabels must be an object mapping exact original locators to display labels')
        return
    sources = canonical_sources(data)
    for raw, display in labels.items():
        if not isinstance(raw, str) or raw not in sources:
            errors.append('sourceLabels key is not an exact canonical source locator: ' + str(raw))
            continue
        if not isinstance(display, str) or not display.strip():
            errors.append('sourceLabels values must be nonempty strings')
        elif number_signature(raw) != number_signature(display):
            errors.append('sourceLabels changed a chapter, page, line, date, or filename number: ' + raw)
        elif locator_signature(raw) != locator_signature(display):
            errors.append('sourceLabels changed the chapter or printed/PDF page assignments: ' + raw)
        elif any(filename not in display for filename in source_filenames(raw)):
            errors.append('sourceLabels must preserve original filenames: ' + raw)
        elif (data.get('meta') or {}).get('language') == 'en':
            visible = without_filenames(display, raw)
            if HAN.search(visible):
                errors.append('English sourceLabels still contain untranslated locator/title text: ' + raw)
    if require_complete and (data.get('meta') or {}).get('language') == 'en':
        missing = sorted(x for x in sources if HAN.search(without_filenames(english_locator_syntax(x), x)) and x not in labels)
        if missing:
            errors.append('English delivery requires reviewed sourceLabels for Chinese citations; original evidence stays unchanged: ' + '; '.join(missing[:3]))


def display_source(value, language=None):
    from localization import LOCALE
    raw = str(value or '')
    if (language or LOCALE.get()) != 'en':
        return raw
    if raw in SOURCE_LABELS.get():
        return SOURCE_LABELS.get()[raw]
    # Compatibility fallback translates locator syntax only. Never guess a title.
    return english_locator_syntax(raw)


def original_disclosure(raw, language=None):
    from localization import LOCALE
    if (language or LOCALE.get()) != 'en' or display_source(raw, language) == raw:
        return ''
    return '<details class="source-original"><summary>Original source label</summary><p>' + escape(raw) + '</p></details>'


def framework_condition(value, language=None):
    from localization import LOCALE
    value = str(value or '').strip()
    if (language or LOCALE.get()) == 'en':
        value = re.sub(r'^(?:(?:applies\s+when\b|when\b)\s*[:：]?\s*)+', '', value, flags=re.I)
        return 'Applies when: ' + value
    value = re.sub(r'^(?:适用\s*[:：]\s*)+', '', value)
    return '适用：' + value


def rule_condition(value, language=None):
    from localization import LOCALE
    value = str(value or '').strip()
    if (language or LOCALE.get()) == 'en':
        prefix = re.match(r'^(when\b\s*[:：]?\s*)', value, re.I)
        if prefix:
            return prefix[1] + re.sub(r'^(?:when\b\s*[:：]?\s*)+', '', value[prefix.end():], flags=re.I)
        # An already complete time/condition phrase does not need another When.
        return value if re.match(r'^(?:if|before|after|during|in|on|once|unless|while|whenever)\b', value, re.I) else 'When ' + value
    if re.match(r'^(?:在|如果|若|一旦|每当|只要|除非|等到|当[前地日年月时场事期下])', value):
        return value
    prefix = re.match(r'^(当\s*)', value)
    if prefix:
        return prefix[1] + re.sub(r'^(?:当(?![前地日年月时场事期下])\s*)+', '', value[prefix.end():])
    return '当 ' + value
