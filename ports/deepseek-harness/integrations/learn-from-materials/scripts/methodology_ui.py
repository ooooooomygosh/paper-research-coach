"""Server-rendered fallbacks for the whole-material view and content sources."""
from html import escape
from methodology import edge_label
from source_presentation import display_source, original_disclosure

def content_sources(unit, language):
    heading='原文出处' if language=='zh-CN' else 'Original sources'
    note='单元页段；未提供更细定位的条目沿用此范围。' if language=='zh-CN' else 'Unit range; items without a finer locator inherit this range.'
    return '<details class="unit-source-disclosure"><summary>'+heading+'</summary><p>'+escape(display_source(unit['source'], language))+'</p><small>'+note+'</small>'+original_disclosure(unit['source'], language)+'</details>'

def overview_markup(data):
    model=data.get('methodology')
    if not model: return ''
    en=data['meta']['language']=='en'
    title='Whole-material methodology' if en else '整份材料的方法论'
    # Template is moved into the action-rules module by the fixed renderer script.
    body='<section class="whole-method" id="wholeMethod">'
    if model['status']=='not-applicable':
        body+='<p>'+escape(model['problem'])+'</p></section>'
        return '<template id="wholeMethodTemplate">'+body+'</template>'
    body+='<div class="method-map" id="methodMap"></div><div id="methodNodeDetail" class="method-node-detail" aria-live="polite" hidden></div>'
    body+='<details class="whole-text"><summary>'+('Complete structure and sources' if en else '完整步骤、逻辑关系与出处')+'</summary>'
    body+='<p>'+escape(model['note'])+'</p><p>'+escape(model['outcome'])+'</p>'
    for n in model['nodes']:
        body+='<h4>'+escape(n['title'])+'</h4><p>'+escape(n['action'])+'</p><p>'+escape(n['output'])+'</p>'
        for s in n['sources']: body+='<p class="relation-source">'+escape(display_source(s['source'], data['meta']['language']))+'</p>'+original_disclosure(s['source'],data['meta']['language'])
        linked=[r for r in data.get('decisionRules',[]) if r.get('id') in n['methodIds']]
        if linked:
            body+='<h5>'+('Related action rules' if en else '关联行动规则')+'</h5>'
            for r in linked:
                body+='<p>'+escape(r['when']+' → '+r['do']+' · '+r['because'])+'</p><p class="relation-source">'+escape(display_source(r['source'], data['meta']['language']))+'</p>'+original_disclosure(r['source'],data['meta']['language'])
    names={n['id']:n['title'] for n in model['nodes']}
    for e in model['edges']:
        relation=(' (' if en else '（')+edge_label(e, data['meta']['language'])+(')' if en else '）')
        body+='<p>'+escape(names[e['from']]+' → '+names[e['to']]+relation+' · '+e['condition']+' · '+e['handoff']+' · '+e['why'])+'</p><p class="relation-source">'+escape(display_source(e['source'], data['meta']['language']))+'</p>'+original_disclosure(e['source'],data['meta']['language'])
    body+='<div class="method-constraints">'
    for c in model['constraints']: body+='<p title="'+escape(display_source(c['source'],data['meta']['language']),quote=True)+'">'+escape(c['text'])+'</p>'+original_disclosure(c['source'],data['meta']['language'])
    body+='</div></details></section>'
    return '<template id="wholeMethodTemplate">'+body+'</template>'
