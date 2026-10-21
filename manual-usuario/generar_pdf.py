"""Build the Cisne Negro handover report from verified content and real captures."""
from pathlib import Path
import json
import html
from collections import defaultdict
from math import ceil
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output/pdf/informe-y-manual-cisne-negro.pdf'
OUT.parent.mkdir(parents=True, exist_ok=True)
D = json.loads((ROOT / 'contenido.json').read_text())
FONT = Path('/System/Library/Fonts/Supplemental')
for name, file in [('Body','Arial.ttf'), ('Bold','Arial Bold.ttf'), ('Display','DIN Condensed Bold.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(FONT / file)))
pdfmetrics.registerFontFamily('Body', normal='Body', bold='Bold')
W,H = 841.89,595.28
INK='#181710'; CREAM='#F3EFE3'; ORANGE='#FF591C'; MUTED='#5F5B50'; GOLD='#DBC07C'
c = canvas.Canvas(str(OUT), pagesize=(W,H), pageCompression=1)
c.setTitle('Cisne Negro | Informe de URLs, accesos y manual de usuario')
c.setAuthor('Softvibes · Cisne Negro')
c.setSubject('Guía ilustrada de la instalación vigente. Credenciales en anexo privado separado.')
pages=[]

def clean(s):
    return s.replace('−','-').replace('＋','+').replace('–','-').replace('—','-').replace('\u2011','-')

def para(s,x,y,w,size=10.5,color=INK,bold=False,leading=None):
    style=ParagraphStyle('p',fontName='Bold' if bold else 'Body',fontSize=size,
        leading=leading or size*1.32,textColor=colors.HexColor(color),spaceAfter=0)
    p=Paragraph(html.escape(clean(s)),style)
    _,h=p.wrap(w,H)
    if y+h>H-31: raise ValueError(f'Page {len(pages)} overflow at {y+h}: {s[:70]}')
    p.drawOn(c,x,H-y-h)
    return y+h

def line(x,y,w,color='#D6D0C2'):
    c.setStrokeColor(colors.HexColor(color));c.setLineWidth(.6)
    c.line(x,H-y,x+w,H-y)

def box(x,y,w,h,fill):
    c.setFillColor(colors.HexColor(fill));c.roundRect(x,H-y-h,w,h,8,stroke=0,fill=1)

def start(title,kicker='MANUAL DE USUARIO',subtitle='',bookmark=None,dark=False):
    pages.append(title)
    bg=INK if dark else CREAM
    c.setFillColor(colors.HexColor(bg));c.rect(0,0,W,H,stroke=0,fill=1)
    c.setFillColor(colors.HexColor(ORANGE));c.rect(0,H-7,W,7,stroke=0,fill=1)
    if bookmark:
        c.bookmarkPage(bookmark);c.addOutlineEntry(title,bookmark,0,False)
    para('CISNE NEGRO',32,22,240,13,CREAM if dark else INK,True)
    para(kicker,540,25,270,8,GOLD if dark else MUTED,True)
    c.setFillColor(colors.HexColor(CREAM if dark else INK));c.setFont('Display',30)
    c.drawString(32,H-82,clean(title.upper()))
    if subtitle: para(subtitle,32,94,W-64,10,GOLD if dark else MUTED)

def finish(dark=False):
    line(32,H-32,W-64,'#4A463B' if dark else '#D6D0C2')
    c.setFillColor(colors.HexColor(GOLD if dark else MUTED));c.setFont('Body',7.4)
    c.drawString(32,18,'CISNE NEGRO  /  '+D['date']+'  /  Uso interno · sin contraseñas')
    c.drawRightString(W-32,18,f'{len(pages):02d}')
    c.showPage()

def shot(filename,x,y,w):
    path=ROOT/'capturas'/filename
    with Image.open(path) as im: iw,ih=im.size
    h=w*ih/iw
    c.drawImage(str(path),x,H-y-h,width=w,height=h,mask='auto')
    return y+h

def link(url,x,y,w,size=9,color='#91421E'):
    bottom=para(url,x,y,w,size,color)
    c.linkURL(url,(x,H-bottom,x+w,H-y),relative=0,thickness=0)
    return bottom

# Cover
start('Detrás de la barra.','INFORME + GUÍA ILUSTRADA',D['subtitle'],bookmark='portada',dark=True)
shot('portada.png',32,129,501)
para('ENLACES, ACCESOS Y GUÍA DE USO.',558,143,245,22,CREAM,True,27)
para('Página · Menú · Pasaporte · CMS · MediaHub · Equipo',558,244,245,13,GOLD,False,19)
para(f"{len(D['urls'])} enlaces y {len(D['pages'])} capítulos con capturas reales de la instalación vigente.",558,317,245,11,CREAM)
link('https://cisnenegro.mx/',558,386,245,12,GOLD)
para(D['introduction'],32,440,775,10.5,CREAM)
para('ACCESOS PRIVADOS: usuarios, contraseñas y PIN se entregan en un archivo separado.',32,516,775,9,GOLD,True)
finish(True)

# A visual orientation / contents page.
start('Encuentra lo que necesitas','MAPA DE LA GUÍA','Elige la tarea; los enlaces del directorio y este índice son clicables.',bookmark='indice')
for n,p in enumerate(D['pages']):
    col=n//10; row=n%10; x=32+col*395; y=137+row*38
    para(f'{n+1:02d}',x,y,28,12,'#A5461F',True)
    para(p['title'],x+35,y,335,11)
    c.linkRect('',p['id'],(x,H-y-30,x+372,H-y),relative=0,thickness=0)
    line(x,y+29,368)
finish()

# Status report. Technical fields are maintained in the data source.
start('Estado de la entrega','INFORME DE INSTALACIÓN','Revisión del 17 de octubre de 2026 · Alcance y comprobaciones',bookmark='estado')
summary=[
 ('Dominio de trabajo','https://cisnenegro.mx/ reúne página principal, menú, CMS, Administración y Equipo. www y HTTP redirigen a HTTPS sin www.'),
 ('Despliegue independiente','Servidor 31.220.63.211: aplicación aislada y datos propios dentro del mismo VPS. Servicio saludable. El alias cisne.softvibes.art entra a la misma instalación y no es un ambiente de pruebas.'),
 ('Dominio anterior','cisnenegro.softvibes.art conserva una instalación y base separadas. Allí siguen las propuestas, análisis y estrategia. Editar ese CMS no actualiza el sitio nuevo.'),
 ('HTTPS y DNS','A @ y A www apuntan a 31.220.63.211, TTL 300. Verificados en las cuatro autoridades. Certificado válido hasta el 16/ene/2027; renovación automática activa. Algunas redes aún pueden conservar caché anterior.'),
 ('Continuidad','Respaldo diario a las 03:55, hora de Ciudad de México; retención de 14 copias. Última ejecución revisada: 17/oct, correcta. Hay una copia externa inicial; falta automatizar su repetición.'),
 ('Antes de la operación real','Asignar accesos individuales al personal y revisar las cuentas de demostración importadas. Confirmar precios, beneficios del Pasaporte y aviso de privacidad con los responsables del negocio.')]
for i,(t,s) in enumerate(summary):
    x=32+(i%2)*395;y=135+(i//2)*129
    box(x,y,378,112,'#E6DFCF');para(t,x+15,y+13,348,12,INK,True)
    para(s,x+15,y+37,348,10)
finish()

# Access model, deliberately no secrets.
start('Quién entra y para qué','PERFILES Y ACCESOS','Tres accesos independientes: CMS, Equipo y Pasaporte.',bookmark='perfiles')
y=132
for role in D['roles']:
    box(32,y,777,69,'#E6DFCF')
    para(role['role'],46,y+11,204,12,INK,True)
    para(role['authentication'],46,y+31,204,9,MUTED)
    para(role['access']+' · '+role['scope'],266,y+12,525,10)
    y+=78
para('Las cuentas vigentes y sus credenciales están en el anexo privado. No se incluyen en capturas ni en esta guía.',32,526,777,9,'#91421E',True)
finish()

# Full directory, 8 links per page for clear labels, permissions and destinations.
urls=D['urls']
groups=ceil(len(urls)/8)
base,extra=divmod(len(urls),groups)
off=0
for group in range(groups):
    count=base+(group<extra)
    start('Directorio de URLs','ENLACES Y PERMISOS',f"Enlaces {off+1}-{off+count} de {len(urls)} · Abre el destino desde el nombre o la dirección.",bookmark=f'urls-{off}')
    for j,u in enumerate(urls[off:off+count]):
        y=132+j*50
        para(u['label'],32,y,270,11,INK,True)
        c.linkURL(u['url'],(32,H-y-16,302,H-y),relative=0,thickness=0)
        para(u['group']+' · '+u['access'],32,y+17,270,8.5,MUTED)
        link(u['url'],319,y,490,9)
        para(u['description'],319,y+16,490,8.6,MUTED)
        line(32,y+43,777)
    off+=count
    finish()

# All how-to pages.
for n,p in enumerate(D['pages']):
    start(p['title'],f"PASO A PASO  /  {n+1:02d}",p.get('subtitle',''),bookmark=p['id'])
    if p.get('screenshot'):
        bottom=shot(p['screenshot'],32,132,472)
        caption=p.get('screenshot_caption','Captura real · alias temporal de la misma instalación. Amplíala en el manual HTML.')
        y=para(caption,32,bottom+8,472,8,MUTED)+10
    else:
        y=para('Edición pública: la captura de esta pantalla administrativa se omite para proteger los datos de cuentas. Los pasos de uso se conservan.',32,140,472,11,MUTED)+24
    for paragraph in p.get('paragraphs',[]):
        y=para(paragraph,32,y,472,10.2)+8
    x=525; w=284; y=133
    para('CÓMO HACERLO',x,y,w,9,'#91421E',True);y+=23
    # Predict height first so no instruction is silently clipped.
    for i,s in enumerate(p.get('steps',[]),1):
        box(x,y,18,18,ORANGE)
        para(str(i),x+5,y+2,13,9,INK,True)
        y=para(s,x+27,y,w-27,10.2)+10
    for tip in p.get('tips',[]):
        y=para('• '+tip,x,y,w,8.9,MUTED)+8
    finish()
    # Two large detail views for the product and media forms.
    for extra in p.get('extra_screenshots',[]):
        detail='Ficha del producto' if 'producto' in extra else 'Ficha del archivo'
        start(detail,'VISTA DE DETALLE',p['title']+' · Pantalla ampliada')
        shot(extra,70,127,702)
        finish()

# Provider entry points and evidence. Account credentials stay private.
start('Soporte y administración técnica','ENTREGA Y CONTINUIDAD','La operación diaria se realiza en el sitio; el servidor y los DNS se administran por separado.',bookmark='soporte')
providers=D.get('providers',[])
if not providers:
    providers=[{'label':'Hostinger · hPanel','url':'https://hpanel.hostinger.com/','description':'Hosting, servidor y dominio según el estado de la transferencia.'},{'label':'Squarespace · DNS de cisnenegro.mx','url':'https://account.squarespace.com/domains/managed/cisnenegro.mx/dns/dns-settings','description':'Gestión de DNS usada durante la migración; puede cambiar cuando concluya la transferencia.'}]
y=137
for p in providers:
    label=p.get('label',p.get('name','Proveedor'))
    y=para(label,32,y,777,13,INK,True)+4
    y=link(p['url'],32,y,777,10)+5
    y=para(p.get('description',p.get('purpose',p.get('notes','Cuenta personal del titular; credenciales no incluidas.'))),32,y,777,10,MUTED)+22
para('EVIDENCIA Y ALCANCE',32,max(y,330),777,11,INK,True)
para('Enlaces comprobados por HTTPS; rutas internas contrastadas con el código desplegado. Capturas obtenidas de la interfaz real, sin publicar contenido, crear socios, cobrar cuentas ni cerrar turnos. Las cifras visibles pueden pertenecer a la demostración importada.',32,max(y,330)+24,777,11)
para('No se verificó en la cuenta del proveedor si ya terminó la transferencia del registrador. Los registros de correo se conservaron según la bitácora de migración.',32,max(y,330)+92,777,10)
para('Para solicitar soporte, envía URL, hora, dispositivo, pasos y error. Oculta contraseñas, PIN y datos de clientes. Entrega el anexo privado solo a los responsables autorizados.',32,max(y,330)+135,777,10)
finish()

c.save()
(ROOT/'tmp/pdfs').mkdir(parents=True, exist_ok=True)
(ROOT/'tmp/pdfs/paginas.json').write_text(json.dumps(pages,ensure_ascii=False,indent=2))
print(f'PDF creado: {len(pages)} páginas; {OUT.stat().st_size:,} bytes')
