import 'dart:convert';
import '../domain/reader_models.dart';

/// Build HTML for read mode.
String buildReadModeHtml({
  required String chapterHtml,
  required List<String> sentences,
  required ContentMode contentMode,
  required List<TranslationPair> pairs,
  required List<ConceptAnnotation> concepts,
  required String bgColor,
  required String textColor,
  required double fontSize,
}) {
  String contentHtml;

  switch (contentMode) {
    case ContentMode.original:
      contentHtml = _buildOriginalHtml(chapterHtml, concepts);
      break;
    case ContentMode.translated:
      contentHtml = _buildTranslatedHtml(sentences, pairs);
      break;
    case ContentMode.bilingual:
      contentHtml = _buildBilingualHtml(sentences, pairs);
      break;
  }

  return _wrapHtml(contentHtml, bgColor: bgColor, textColor: textColor, fontSize: fontSize);
}

String _buildOriginalHtml(String html, List<ConceptAnnotation> concepts) {
  // Inject concept badges into HTML
  String result = html;
  if (concepts.isNotEmpty) {
    // Sort by badge number descending to avoid offset issues
    final sorted = [...concepts]..sort((a, b) => b.badgeNumber.compareTo(a.badgeNumber));
    for (final c in sorted) {
      final badgeClass = c.category == 'cultural_context' ? 'concept-badge-cultural' : 'concept-badge';
      final badge = '<sup class="$badgeClass" onclick="onConceptTap(\'${_escapeJs(c.conceptId)}\', \'${_escapeJs(c.term)}\', \'${_escapeJs(c.definition ?? '暂无定义')}\')">${_circledNumber(c.badgeNumber)}</sup>';
      // Insert badge after first occurrence of the term
      final termIdx = result.indexOf(c.term);
      if (termIdx >= 0) {
        result = result.substring(0, termIdx + c.term.length) + badge + result.substring(termIdx + c.term.length);
      }
    }
  }
  return result;
}

String _buildTranslatedHtml(List<String> sentences, List<TranslationPair> pairs) {
  final buffer = StringBuffer();
  for (int i = 0; i < sentences.length; i++) {
    final text = i < pairs.length ? pairs[i].translated : sentences[i];
    buffer.writeln('<p data-index="$i">${_escapeHtml(text)}</p>');
  }
  return buffer.toString();
}

String _buildBilingualHtml(List<String> sentences, List<TranslationPair> pairs) {
  final buffer = StringBuffer();
  for (int i = 0; i < sentences.length; i++) {
    final original = sentences[i];
    final translated = i < pairs.length ? pairs[i].translated : '';
    buffer.writeln('<div class="bilingual-row" data-index="$i">');
    buffer.writeln('  <div class="bilingual-original">${_escapeHtml(original)}</div>');
    if (translated.isNotEmpty) {
      buffer.writeln('  <div class="bilingual-translated">${_escapeHtml(translated)}</div>');
    }
    buffer.writeln('</div>');
  }
  return buffer.toString();
}

String _wrapHtml(String content, {
  required String bgColor,
  required String textColor,
  required double fontSize,
}) {
  final escapedContent = jsonEncode(content);

  return '''
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html {
    -webkit-overflow-scrolling: touch;
  }
  body {
    background-color: $bgColor;
    color: $textColor;
    font-size: ${fontSize}px;
    line-height: 1.8;
    padding: 16px 20px 80px;
    word-wrap: break-word;
    overflow-wrap: break-word;
    -webkit-text-size-adjust: 100%;
  }
  p, div, li, blockquote, h1, h2, h3, h4, h5, h6 {
    margin-bottom: 0.8em;
  }
  h1 { font-size: 1.4em; font-weight: bold; }
  h2 { font-size: 1.2em; font-weight: bold; }
  h3 { font-size: 1.1em; font-weight: bold; }
  img { max-width: 100%; height: auto; }
  a { color: inherit; text-decoration: underline; }

  /* Concept badges */
  .concept-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px; height: 18px;
    font-size: 10px;
    font-weight: 600;
    background: #7c3aed;
    color: white;
    border-radius: 50%;
    margin-left: 2px;
    cursor: pointer;
    vertical-align: super;
    line-height: 1;
  }
  .concept-badge-cultural {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px; height: 18px;
    font-size: 10px;
    font-weight: 600;
    background: #f59e0b;
    color: white;
    border-radius: 50%;
    margin-left: 2px;
    cursor: pointer;
    vertical-align: super;
    line-height: 1;
  }

  /* Bilingual layout */
  .bilingual-row {
    margin-bottom: 1em;
    padding: 8px 0;
    border-bottom: 1px solid rgba(128,128,128,0.1);
  }
  .bilingual-original {
    margin-bottom: 4px;
  }
  .bilingual-translated {
    opacity: 0.7;
    font-style: italic;
  }

  /* Selection highlight */
  ::selection {
    background: rgba(76, 175, 80, 0.3);
  }
</style>
</head>
<body>
<div id="content"></div>
<script>
  document.getElementById('content').innerHTML = $escapedContent;

  // Add data-index to top-level block elements
  (function() {
    var elems = document.querySelectorAll('#content > p, #content > div, #content > h1, #content > h2, #content > h3, #content > h4, #content > h5, #content > h6, #content > li, #content > blockquote');
    for (var i = 0; i < elems.length; i++) {
      if (!elems[i].hasAttribute('data-index')) {
        elems[i].setAttribute('data-index', i);
      }
    }
  })();

  // Concept tap handler
  function onConceptTap(id, term, definition) {
    window.FlutterChannel.postMessage(JSON.stringify({
      type: 'conceptTap',
      conceptId: id,
      term: term,
      definition: definition
    }));
  }

  // Center tap for toolbar toggle
  var tapStartTime = 0, tapStartX = 0, tapStartY = 0;
  document.addEventListener('touchstart', function(e) {
    tapStartTime = Date.now();
    tapStartX = e.touches[0].clientX;
    tapStartY = e.touches[0].clientY;
  });
  document.addEventListener('touchend', function(e) {
    var dt = Date.now() - tapStartTime;
    if (dt > 300) return;
    var endX = e.changedTouches[0].clientX;
    var endY = e.changedTouches[0].clientY;
    if (Math.abs(endX - tapStartX) > 10 || Math.abs(endY - tapStartY) > 10) return;
    var w = window.innerWidth, h = window.innerHeight;
    if (endX > w/3 && endX < w*2/3 && endY > h/3 && endY < h*2/3) {
      window.FlutterChannel.postMessage(JSON.stringify({type: 'centerTap'}));
    }
  });

  // Scroll reporting
  var scrollTimer = null;
  window.addEventListener('scroll', function() {
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(function() {
      var elems = document.querySelectorAll('[data-index]');
      var viewTop = window.scrollY + window.innerHeight * 0.3;
      var best = null;
      for (var i = 0; i < elems.length; i++) {
        if (elems[i].offsetTop <= viewTop) best = elems[i];
      }
      if (best) {
        window.FlutterChannel.postMessage(JSON.stringify({
          type: 'scroll',
          index: parseInt(best.getAttribute('data-index'))
        }));
      }
    }, 200);
  });

  // Text selection handler
  document.addEventListener('selectionchange', function() {
    var sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.toString().trim()) return;
    var range = sel.getRangeAt(0);
    var rect = range.getBoundingClientRect();
    window.FlutterChannel.postMessage(JSON.stringify({
      type: 'selection',
      text: sel.toString(),
      top: rect.top + window.scrollY,
      left: rect.left + rect.width / 2
    }));
  });

  // Theme update
  function updateTheme(bg, text, size) {
    document.body.style.backgroundColor = bg;
    document.body.style.color = text;
    document.body.style.fontSize = size + 'px';
  }

  // Scroll to paragraph
  function scrollToSentence(index) {
    var el = document.querySelector('[data-index="' + index + '"]');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
</script>
</body>
</html>
''';
}

String _escapeHtml(String text) {
  return text
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;');
}

String _escapeJs(String text) {
  return text
      .replaceAll('\\', '\\\\')
      .replaceAll("'", "\\'")
      .replaceAll('\n', '\\n');
}

String _circledNumber(int n) {
  if (n >= 1 && n <= 20) {
    return String.fromCharCode(0x2460 + n - 1); // ①②③...
  }
  return '($n)';
}
