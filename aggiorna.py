#!/usr/bin/env python3
"""Scrive i risultati DENTRO index.html.

Questo e' il cuore del fix: invece di far chiedere i dati a Google al
visitatore — che aspetta uno o due secondi guardando una tabella vuota — i
risultati stanno gia' scritti nella pagina. Chi apre il sito li vede subito.

Lo stesso script gira ogni mezz'ora dentro GitHub (vedi
.github/workflows/aggiorna-dati.yml): rilegge il foglio e riscrive solo i
pezzi fra i marcatori, senza toccare nient'altro della pagina.

Uso:  python3 aggiorna.py [index.html]
"""
import io, json, os, re, sys, urllib.request

FOGLIO = ('https://docs.google.com/spreadsheets/d/e/'
          '2PACX-1vRSMpVqf32wIcmha6LvP3hhkdHzLu5KdOpKM5gejPbds6wE5KzTZIdxzkr6z5t-U7XqhCqUEiCBmB_H'
          '/pub?gid=0&single=true&output=csv')

MESI = ['gen','feb','mar','apr','mag','giu','lug','ago','set','ott','nov','dic']


def leggi_csv(testo):
    """Stesse regole del lettore che sta nella pagina, cosi' i due risultati
    coincidono e non si vede nessuno sfarfallio quando arriva l'aggiornamento."""
    righe = testo.strip().split('\n')
    if len(righe) < 2:
        return []
    pulisci = lambda v: v.strip().strip('"').strip()
    intest = [pulisci(h).lower() for h in righe[0].split(',')]
    fuori = []
    for riga in righe[1:]:
        vals, corr, tra_virgolette = [], '', False
        for ch in riga:
            if ch == '"':
                tra_virgolette = not tra_virgolette
            elif ch == ',' and not tra_virgolette:
                vals.append(corr.strip()); corr = ''
            else:
                corr += ch
        vals.append(corr.strip())
        r = {}
        for i, h in enumerate(intest):
            k = {'p/l': 'pl', 'win rate': 'rr'}.get(h, h)
            r[k] = vals[i] if i < len(vals) else ''
        if r.get('data'):
            fuori.append(r)
    return fuori


def data_it(s):
    """«17/03/2026» -> «17 mar 2026». Stesso identico formato del browser."""
    try:
        if '/' in s:
            g, m, a = s.split('/')[:3]
            return '%02d %s %s' % (int(g), MESI[int(m) - 1], a)
    except Exception:
        pass
    return s


def esc(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def numero_davanti(v):
    """Come fa parseFloat nel browser: legge il numero all'inizio e ignora il
    resto. Serve perche' il testo prodotto qui deve venire IDENTICO a quello
    che produrrebbe la pagina, se no la tabella si ridisegna per niente."""
    m = re.match(r'\s*[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?', str(v or ''))
    if not m or not m.group(0).strip():
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def numero_come_js(f):
    """Un numero scritto come lo scrive JavaScript: 30.0 diventa «30»."""
    if f == int(f) and abs(f) < 1e21:
        return str(int(f))
    return repr(f)


def indirizzo_buono(u):
    """Nel bottone Video ci finiscono solo indirizzi web veri."""
    return bool(re.match(r'^https?://', str(u or '').strip(), re.I))


ICONA = ('<svg viewBox="0 0 16 16" fill="none">'
         '<path d="M6 4l6 4-6 4V4z" fill="currentColor"/></svg>')


def righe_html(sessioni, filtro='all'):
    """Specchio esatto di costruisciRighe() dentro la pagina. Se cambi una
    virgola qui, cambiala anche li': i due testi devono coincidere."""
    if filtro == 'win':
        sessioni = [s for s in sessioni if (s.get('esito') or '').upper() == 'WIN']
    elif filtro == 'loss':
        sessioni = [s for s in sessioni if (s.get('esito') or '').upper() == 'LOSS']

    out = []
    for s in reversed(sessioni):
        pl = numero_davanti(s.get('pl'))
        if pl is None:
            cl_pl, txt_pl = 'pl-na', '\u2014'
        else:
            cl_pl = 'pl-positive' if pl >= 0 else 'pl-negative'
            txt_pl = ('+' if pl >= 0 else '') + numero_come_js(pl)

        mae = ('-' + s['mae']) if s.get('mae') else '\u2014'
        rr = s.get('rr') or '\u2014'

        bias = (s.get('bias') or '').upper()
        cl_dir = 'dir-long' if bias == 'LONG' else ('dir-short' if bias == 'SHORT' else '')
        txt_dir = '\u25b2 LONG' if bias == 'LONG' else (
            '\u25bc SHORT' if bias == 'SHORT' else (bias or '\u2014'))

        es = (s.get('esito') or '').upper()
        cl_es = {'WIN': 'esito-win', 'LOSS': 'esito-loss', 'BE': 'esito-be'}.get(es, 'esito-neutral')

        video = (s.get('video') or '').strip()
        cella = ('<a href="%s" target="_blank" rel="noopener noreferrer" class="video-btn">%sVideo</a>'
                 % (esc(video), ICONA)) if indirizzo_buono(video) else '<span class="no-video">\u2014</span>'

        out.append(
            '<tr>'
            '<td class="entry-val">%s</td>'
            '<td><span class="%s">%s</span></td>'
            '<td class="entry-val">%s</td>'
            '<td class="stop-val">%s</td>'
            '<td class="entry-val">%s</td>'
            '<td class="mae-val">%s</td>'
            '<td class="%s">%s</td>'
            '<td>%s</td>'
            '<td><span class="%s">%s</span></td>'
            '<td>%s</td>'
            '</tr>' % (
                esc(data_it(s.get('data', ''))), cl_dir, esc(txt_dir),
                esc(s.get('entrata') or '\u2014'), esc(s.get('stop') or '\u2014'),
                esc(s.get('uscita') or '\u2014'), esc(mae), cl_pl, esc(txt_pl),
                esc(rr), cl_es, esc(es or '\u2014'), cella))
    return ''.join(out)


def conti(sessioni):
    reali = [s for s in sessioni if (s.get('esito') or '').upper() in ('WIN', 'LOSS')]
    win = sum(1 for s in reali if s['esito'].upper() == 'WIN')
    loss = len(reali) - win
    wr = ('%.1f' % (win / len(reali) * 100)) if reali else '0.0'
    tot = 0.0
    for s in reali:
        n = numero_davanti(s.get('pl'))
        if n is not None:
            tot += n
    return {
        'sessioni': str(len(reali)),
        'wl': '%dW / %dL' % (win, loss),
        'wr': wr + '<span class="kpi-unit">%</span>',
        'pl': ('+' if tot >= 0 else '') + ('%.1f' % tot) + '<span class="kpi-unit">pt</span>',
        'conta': '%d sessioni' % len(sessioni),
    }


def sostituisci(html, nome, dentro):
    a, b = '<!--%s-->' % nome, '<!--/%s-->' % nome
    if a not in html or b not in html:
        raise SystemExit('marcatore %s non trovato nella pagina' % nome)
    pre, resto = html.split(a, 1)
    _, post = resto.split(b, 1)
    return pre + a + dentro + b + post


def main():
    percorso = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'index.html')
    req = urllib.request.Request(FOGLIO, headers={'User-Agent': 'aggiorna-dati/1.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        testo = r.read().decode('utf-8')
    sessioni = leggi_csv(testo)
    if len(sessioni) < 10:
        raise SystemExit('il foglio ha restituito solo %d righe: non tocco niente'
                         % len(sessioni))

    html = io.open(percorso, encoding='utf-8').read()
    k = conti(sessioni)
    # il </ va spezzato, se no un indirizzo strano nel foglio chiuderebbe il tag
    dati = json.dumps(sessioni, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    html = sostituisci(html, 'DATI-JSON',
                       '<script type="application/json" id="dati-sessioni">%s</script>' % dati)
    html = sostituisci(html, 'DATI-RIGHE', righe_html(sessioni))
    html = sostituisci(html, 'DATI-SESSIONI', k['sessioni'])
    html = sostituisci(html, 'DATI-WL', k['wl'])
    html = sostituisci(html, 'DATI-WR', k['wr'])
    html = sostituisci(html, 'DATI-PL', k['pl'])
    html = sostituisci(html, 'DATI-CONTA', k['conta'])
    io.open(percorso, 'w', encoding='utf-8').write(html)
    print('scritte %d sessioni (%s operazioni, %s) dentro %s'
          % (len(sessioni), k['sessioni'], k['wl'], os.path.basename(percorso)))


if __name__ == '__main__':
    main()
