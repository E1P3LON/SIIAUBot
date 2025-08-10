import logging
import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Set
import tempfile
from html.parser import HTMLParser
from urllib import request
import ssl
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Parser personalizado para extraer información de la página de SIIAU
# Hereda de HTMLParser para procesar el HTML de la página de materias
class ParserUDG(HTMLParser):
    """
    Parser para extraer información de materias del HTML de SIIAU.
    Procesa las tablas de materias y extrae la información relevante.
    """
    def __init__(self):
        super().__init__()
        self.lastTag = ""      # Último tag HTML procesado
        self.lastClass = ""    # Última clase CSS encontrada
        self.i = 0            # Contador para el nivel de anidamiento
        self.datos = []       # Almacena los datos extraídos
    def handle_starttag(self, tag, attrs):
        self.lastTag = tag
        self.lastClass = ""
        for attr in attrs:
            if attr[0] == 'class':
                self.lastClass = attr[1]
        if tag == 'table':
            d = self.datos
            for j in range(self.i):
                d = d[-1]
            d.append([])
            self.i += 1
        if tag == 'tr':
            d = self.datos
            for j in range(self.i):
                d = d[-1]
            d.append([])
            self.i += 1
    def handle_endtag(self, tag):
        self.lastTag = ""
        self.lastClass = ""
        if tag == 'table':
            self.i -= 1
        if tag == 'tr':
            self.i -= 1
    def handle_data(self, data):
        if self.lastTag == "td" and data != '' and data[0] != '\\' and data.isascii():
            d = self.datos
            for j in range(self.i):
                d = d[-1]
            d.append(data)
        if self.lastTag == "a":
            d = self.datos
            for j in range(self.i):
                d = d[-1]
            d.append(data)
    def feed_datos(self, str_data, datos):
        self.datos = datos
        self.feed(str_data)

# Clase que representa una materia en SIIAU
class Clase:
    """
    Representa una materia del SIIAU con toda su información asociada.
    Proporciona métodos para acceder a los datos de la materia como NRC,
    nombre, profesor, horarios y cupos disponibles.
    """
    # Índices para acceder a la información en el array de datos
    Prop = {
        "CU": 0,      # Centro Universitario
        "NRC": 1,     # Número de Referencia del Curso
        "Clave": 2,   # Clave de la materia
        "Materia": 3, # Nombre de la materia
        "Sec": 4,     # Sección
        "CR": 5,      # Créditos
        "CUP": 6,     # Cupos totales
        "DIS": 7,     # Cupos disponibles
        "Horario": 8, # Información de horarios
        "Profesor": 9 # Información del profesor
    }
    # Índices para la información de horarios
    Horarios = {
        "Ses": 0,     # Sesión
        "Hora": 1,    # Hora
        "Dias": 2,    # Días
        "Edif": 3,    # Edificio
        "Aula": 4,    # Aula
        "Periodo": 5  # Periodo
    }
    # Índices para la información del profesor
    Profesor = {
        "Ses": 0,     # Sesión
        "Profesor": 1 # Nombre del profesor
    }
    def __init__(self, datos, baseDatos):
        self.baseDatos = baseDatos
        self.datos = datos
        baseDatos.NRCDict[self.getNRC()] = self
        if self.getClave() not in baseDatos.ClaveDict:
            baseDatos.ClaveDict[str(self.getClave())] = {}
        baseDatos.ClaveDict[str(self.getClave())][self.getNRC()] = self
    def get(self, prop):
        p = Clase.Prop[prop]
        return self.datos[p]
    def getMateria(self):
        return self.datos[3]
    def getNombre(self):
        return self.getMateria()
    def getNRC(self):
        return self.datos[1]
    def getClave(self):
        return self.datos[2]
    def getProfesor(self, n=0, arg="Profesor"):
        if len(self.datos) > 9 and isinstance(self.datos[9], list) and len(self.datos[9]) > n:
            if isinstance(self.datos[9][n], list) and len(self.datos[9][n]) > Clase.Profesor[arg]:
                return self.datos[9][n][Clase.Profesor[arg]]
            elif isinstance(self.datos[9][n], str):
                return self.datos[9][n]
        return "No asignado"
    def getHorarios(self):
        if len(self.datos) > 8 and isinstance(self.datos[8], list) and len(self.datos[8]) > 0:
            return self.datos[8][0] if isinstance(self.datos[8][0], list) else str(self.datos[8][0])
        return "No definido"
    
    # Métodos adicionales para compatibilidad con el monitoreo
    def tiene_cupos(self):
        """Verifica si la materia tiene cupos disponibles"""
        try:
            disponibles = int(self.get('DIS'))
            return disponibles > 0
        except (ValueError, TypeError):
            return False
    
    def cupos_disponibles(self):
        """Retorna el número de cupos disponibles"""
        try:
            return int(self.get('DIS'))
        except (ValueError, TypeError):
            return 0
    
    def cupos_totales(self):
        """Retorna el número total de cupos"""
        try:
            return int(self.get('CUP'))
        except (ValueError, TypeError):
            return 0
    
    def porcentaje_ocupacion(self):
        """Calcula el porcentaje de ocupación"""
        try:
            total = self.cupos_totales()
            disponibles = self.cupos_disponibles()
            if total > 0:
                ocupados = total - disponibles
                return (ocupados / total) * 100
            return 0
        except:
            return 0
    
    def info_cupos(self):
        """Retorna información formateada de cupos"""
        return (f"📚 *{self.getNombre()}*\n"
                f"🔢 NRC: `{self.getNRC()}`\n"
                f"📝 Clave: `{self.getClave()}`\n"
                f"👥 Cupos: {self.cupos_disponibles()}/{self.cupos_totales()}\n"
                f"👨‍🏫 Profesor: {self.getProfesor()}\n"
                f"🕐 Horario: {self.getHorarios()}")
    
    def __str__(self):
        return str(self.datos)
    @staticmethod
    def isClave(code):
        return type(code)==str and code[0]=='I'

# BaseDatos adaptada para usar el URL fijo y lógica Limabot
class BaseDatos:
    def __init__(self, ciclo = "202520"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        url = "https://siiauescolar.siiau.udg.mx/wal/sspseca.consulta_oferta?ciclop=" + ciclo + "&cup=&majrp=ICOM&mostrarp=1000000"
        try:
            body = request.urlopen(url, context=ctx).read()
        except Exception as e:
            logging.error(f"No se pudo obtener la página SIIAU: {e}")
            self.Datos = []
            self.NRCDict = {}
            self.ClaveDict = {}
            self.Clases = []
            return
        Datos = []
        parser = ParserUDG()
        parser.feed_datos(str(body), Datos)
        if not Datos or not isinstance(Datos, list) or len(Datos) == 0 or not isinstance(Datos[0], list):
            logging.warning("No se pudieron extraer materias de SIIAU: formato inesperado")
            self.Datos = []
            self.NRCDict = {}
            self.ClaveDict = {}
            self.Clases = []
            return
        self.Datos = Datos[0]
        self.NRCDict = {}
        self.ClaveDict = {}
        self.Clases = []
        for d in self.Datos:
            if isinstance(d, list) and len(d) >= 10:
                try:
                    self.Clases.append(Clase(d, self))
                except Exception as e:
                    logging.error(f"Error procesando materia: {e}, datos: {d}")
        # Limpiar clases vacías
        # Puedes agregar limpia(self.Clases) si lo necesitas
    def findNRC(self, nrc):
        if type(nrc) == list:
            return [self.find(i) for i in nrc]
        return self.NRCDict.get(nrc)
    def findClave(self, clave):
        if type(clave) == list:
            l = []
            for c in clave:
                l += list(self.ClaveDict[c].values())
            return l
        return list(self.ClaveDict[clave].values())
    def find(self, code):
        if Clase.isClave(code):
            return self.findClave(code)
        return self.findNRC(code)

# ActualizarBases para futuras extensiones (multi-ciclo, multi-URL)
def ActualizarBases():
    # Solo usa el URL fijo, pero puedes extender para otros ciclos si lo deseas
    global Ciclo, Calendarios
    Ciclo = {}
    Calendarios = ["202520"]
    Ciclo["202520"] = BaseDatos("202520")

class SiiauMonitor:
    """
    Clase principal para monitorear SIIAU.
    Se encarga de obtener y mantener actualizados los datos de las materias.
    
    Atributos:
        ctx: Contexto SSL para las conexiones HTTPS
        materias_cache: Diccionario que almacena las materias por NRC
    """
    
    def __init__(self):
        # Configuración del contexto SSL para permitir conexiones a SIIAU
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        # Cache de materias para evitar consultas repetidas
        self.materias_cache = {}

    def obtener_datos_siiau(self):
        """Obtiene todas las materias de ICOM usando BaseDatos y NRCs"""
        try:
            bd = BaseDatos("202520")
            self.materias_cache = bd.NRCDict
            logger.info(f"Obtenidas {len(self.materias_cache)} materias de ICOM")
            return self.materias_cache
        except Exception as e:
            logger.error(f"Error al obtener datos de SIIAU: {e}")
            return {}

    def buscar_materia(self, codigo):
        """Busca una materia por NRC o Clave"""
        # Buscar por NRC
        if codigo in self.materias_cache:
            return self.materias_cache[codigo]
        
        # Buscar por Clave
        for materia in self.materias_cache.values():
            if materia.getClave() == codigo:
                return materia
        
        return None

class CuposBot:
    """Bot de Telegram para monitorear cupos"""
    
    def __init__(self):
        self.monitor = SiiauMonitor()
        self.suscripciones = {}  # {user_id: {nrc: {threshold: int, last_notified: datetime}}}
        self.data_file = "suscripciones.json"
        self.cargar_suscripciones()

    def cargar_suscripciones(self):
        """Carga suscripciones desde archivo"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    # Convertir strings de datetime de vuelta a datetime objects
                    for user_id, subs in data.items():
                        for nrc, info in subs.items():
                            if 'last_notified' in info and info['last_notified']:
                                info['last_notified'] = datetime.fromisoformat(info['last_notified'])
                    self.suscripciones = data
                logger.info(f"Cargadas suscripciones para {len(self.suscripciones)} usuarios")
        except Exception as e:
            logger.error(f"Error cargando suscripciones: {e}")
            self.suscripciones = {}

    def guardar_suscripciones(self):
        """Guarda suscripciones a archivo"""
        try:
            # Convertir datetime objects a strings para JSON
            data_to_save = {}
            for user_id, subs in self.suscripciones.items():
                data_to_save[user_id] = {}
                for nrc, info in subs.items():
                    data_to_save[user_id][nrc] = info.copy()
                    if 'last_notified' in info and info['last_notified']:
                        data_to_save[user_id][nrc]['last_notified'] = info['last_notified'].isoformat()
                    else:
                        data_to_save[user_id][nrc]['last_notified'] = None
            
            with open(self.data_file, 'w') as f:
                json.dump(data_to_save, f, indent=2)
        except Exception as e:
            logger.error(f"Error guardando suscripciones: {e}")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start"""
        mensaje = """
🤖 *¡Bienvenido al Bot Monitor de Cupos SIIAU!*

Este bot te ayuda a monitorear los cupos disponibles de materias en SIIAU Escolar.

*Comandos disponibles:*
`/suscribir [NRC/Clave]` - Suscribirse a una materia
`/desuscribir [NRC/Clave]` - Desuscribirse de una materia  
`/mis_suscripciones` - Ver tus suscripciones activas
`/verificar [NRC/Clave]` - Verificar cupos actuales
`/buscar [término]` - Buscar materias
`/ayuda` - Mostrar ayuda detallada

¡Comienza suscribiéndote a una materia! 📚
        """
        await update.message.reply_text(mensaje, parse_mode='Markdown')

    async def ayuda(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /ayuda"""
        mensaje = """
📖 *Ayuda del Bot Monitor de Cupos*

*Comandos principales:*

🔔 `/suscribir [NRC/Clave]`
   Ejemplo: `/suscribir 12345` o `/suscribir I5919`
   Te notificaré cuando haya cupos disponibles.

🔕 `/desuscribir [NRC/Clave]`  
   Cancela las notificaciones de una materia.

📋 `/mis_suscripciones`
   Muestra todas tus suscripciones activas.

🔍 `/verificar [NRC/Clave]`
   Consulta los cupos actuales de una materia.

🔎 `/buscar [término]`
   Busca materias por nombre, clave o NRC.

*Notas importantes:*
• El bot verifica cupos cada 10 segundos
• Solo te notifica cuando hay cupos disponibles
• Puedes suscribirte a múltiples materias
• Los datos se actualizan automáticamente
        """
        await update.message.reply_text(mensaje, parse_mode='Markdown')

    async def suscribir(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /suscribir mejorado: requiere clave y NRC"""
        if len(context.args) < 1:
            await update.message.reply_text("❌ Proporciona el NRC.\nEjemplo: `/suscribir 216502`", parse_mode='Markdown')
            return

        nrc = context.args[0].strip()
        user_id = str(update.effective_user.id)

        await update.message.reply_text(f"🔄 Buscando información de NRC {nrc} en SIIAU...")
        bd = BaseDatos()
        clase = bd.findNRC(nrc)

        if not clase:
            await update.message.reply_text(f"❌ No se encontró la materia con NRC `{nrc}`.", parse_mode='Markdown')
            return

        if user_id not in self.suscripciones:
            self.suscripciones[user_id] = {}

        self.suscripciones[user_id][clase.getNRC()] = {
            'codigo': f"{nrc}",
            'nombre': clase.getNombre(),
            'profesor': clase.getProfesor(),
            'cupos': clase.get('CUP'),
            'disponibles': clase.get('DIS'),
            'threshold': 1,
            'last_notified': None
        }
        self.guardar_suscripciones()

        mensaje = f"✅ *Suscripción activada*\n\n{clase.info_cupos()}\n\nTe notificaré cuando tenga cupos disponibles."
        await update.message.reply_text(mensaje, parse_mode='Markdown')

    async def desuscribir(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /desuscribir"""
        if not context.args:
            await update.message.reply_text("❌ Proporciona un NRC o Clave.\nEjemplo: `/desuscribir 12345`", parse_mode='Markdown')
            return

        codigo = context.args[0].strip()
        user_id = str(update.effective_user.id)

        if user_id not in self.suscripciones:
            await update.message.reply_text("❌ No tienes suscripciones activas.")
            return

        # Buscar por NRC directo o por código guardado
        nrc_a_eliminar = None
        for nrc, info in self.suscripciones[user_id].items():
            if nrc == codigo or info['codigo'] == codigo:
                nrc_a_eliminar = nrc
                break

        if not nrc_a_eliminar:
            await update.message.reply_text(f"❌ No estás suscrito a la materia: `{codigo}`", parse_mode='Markdown')
            return

        materia_info = self.suscripciones[user_id][nrc_a_eliminar]
        del self.suscripciones[user_id][nrc_a_eliminar]
        
        if not self.suscripciones[user_id]:
            del self.suscripciones[user_id]

        self.guardar_suscripciones()
        
        await update.message.reply_text(f"✅ Te has desuscrito de: *{materia_info['nombre']}*", parse_mode='Markdown')

    async def mis_suscripciones(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /mis_suscripciones"""
        user_id = str(update.effective_user.id)
        
        if user_id not in self.suscripciones or not self.suscripciones[user_id]:
            await update.message.reply_text("❌ No tienes suscripciones activas.\nUsa `/suscribir [NRC/Clave]` para comenzar.", parse_mode='Markdown')
            return

        mensaje = "📋 *Tus suscripciones activas:*\n\n"
        # Obtener datos actualizados
        materias = self.monitor.obtener_datos_siiau()
        for nrc, info in self.suscripciones[user_id].items():
            materia = materias.get(nrc)
            if materia:
                status = "✅" if materia.tiene_cupos() else "❌"
                mensaje += f"• {status} *{materia.getNombre()}*\n"
                mensaje += f"  🔢 NRC: `{materia.getNRC()}`\n"
                mensaje += f"  📝 Clave: `{materia.getClave()}`\n"
                mensaje += f"  👥 Cupos: {materia.cupos_disponibles()}/{materia.cupos_totales()}\n"
                mensaje += f"  👨‍🏫 Profesor: {materia.getProfesor()}\n"
                mensaje += f"  🕐 Horario: {materia.getHorarios()}\n\n"
            else:
                mensaje += f"• ❌ *{info['nombre']}* (NRC: `{nrc}`)\n"
                mensaje += f"  ⚠️ No encontrada en ciclo actual\n\n"
        mensaje += f"📊 Total: {len(self.suscripciones[user_id])} suscripciones"
        await update.message.reply_text(mensaje, parse_mode='Markdown')

    async def verificar(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /verificar"""
        if not context.args:
            await update.message.reply_text("❌ Proporciona un NRC o Clave.\nEjemplo: `/verificar 12345`", parse_mode='Markdown')
            return

        codigo = context.args[0].strip()
        
        await update.message.reply_text("🔄 Consultando SIIAU...")
        materias = self.monitor.obtener_datos_siiau()
        if not materias:
            await update.message.reply_text("❌ No se pudieron obtener datos de SIIAU.")
            return
        
        materia = self.monitor.buscar_materia(codigo)
        if not materia:
            await update.message.reply_text(f"❌ No se encontró la materia: `{codigo}`", parse_mode='Markdown')
            return
        
        mensaje = f"🔍 *Consulta actual:*\n\n{materia.info_cupos()}"
        if materia.tiene_cupos():
            mensaje += "\n\n✅ *¡Hay cupos disponibles!*"
        else:
            mensaje += "\n\n❌ *Sin cupos disponibles*"
        await update.message.reply_text(mensaje, parse_mode='Markdown')

    async def buscar(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /buscar"""
        if not context.args:
            await update.message.reply_text("❌ Proporciona un término de búsqueda.\nEjemplo: `/buscar algebra`", parse_mode='Markdown')
            return

        termino = " ".join(context.args).lower()
        
        await update.message.reply_text("🔍 Buscando en SIIAU...")
        materias = self.monitor.obtener_datos_siiau()
        if not materias:
            await update.message.reply_text("❌ No se pudieron obtener datos de SIIAU.")
            return
        
        resultados = []
        for materia in materias.values():
            if (termino in materia.getNombre().lower() or 
                termino in materia.getClave().lower() or 
                termino in materia.getNRC()):
                resultados.append(materia)
        
        if not resultados:
            await update.message.reply_text(f"❌ No se encontraron materias con: `{termino}`", parse_mode='Markdown')
            return
        
        # Limitar a 10 resultados
        resultados = resultados[:10]
        mensaje = f"🔍 *Resultados para '{termino}':*\n\n"
        for materia in resultados:
            status = "✅" if materia.tiene_cupos() else "❌"
            mensaje += f"• {status} *{materia.getNombre()}*\n"
            mensaje += f"  🔢 NRC: `{materia.getNRC()}`\n"
            mensaje += f"  📝 Clave: `{materia.getClave()}`\n"
            mensaje += f"  👥 Cupos: {materia.cupos_disponibles()}/{materia.cupos_totales()}\n"
            mensaje += f"  👨‍🏫 Profesor: {materia.getProfesor()}\n"
            mensaje += f"  🕐 Horario: {materia.getHorarios()}\n\n"

        if len(resultados) == 10:
            mensaje += f"... y más resultados disponibles"
        await update.message.reply_text(mensaje, parse_mode='Markdown')

    async def monitorear_cupos(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Función que monitorea los cupos periódicamente"""
        logger.info("Iniciando verificación de cupos cada 10 segundos...")
        try:
            if not self.suscripciones:
                return

            materias = self.monitor.obtener_datos_siiau()
            if not materias:
                logger.warning("No se pudieron obtener datos de SIIAU")
                return

            # Para cada usuario y sus suscripciones
            for user_id, suscripciones_usuario in self.suscripciones.items():
                if not suscripciones_usuario:
                    continue

                # Verificar cada suscripción
                for nrc, info_suscripcion in suscripciones_usuario.items():
                    materia = materias.get(nrc)
                    if not materia:
                        continue

                    # Si tiene cupos y no hemos notificado recientemente
                    if (materia.tiene_cupos() and 
                        (info_suscripcion.get('last_notified') is None or 
                         datetime.now() - info_suscripcion['last_notified'] > timedelta(hours=1))):
                        
                        mensaje_cupos = f"🎉 *¡ALERTA DE CUPOS!*\n\n{materia.info_cupos()}\n\n" \
                                      f"¡Date prisa para inscribirte! 🏃‍♂️💨"
                        try:
                            await context.bot.send_message(
                                chat_id=int(user_id),
                                text=mensaje_cupos,
                                parse_mode='Markdown'
                            )
                            info_suscripcion['last_notified'] = datetime.now()
                            logger.info(f"Notificación enviada a {user_id} para NRC {nrc}")
                        except Exception as e:
                            logger.error(f"Error enviando notificación a {user_id}: {e}")

            self.guardar_suscripciones()

        except Exception as e:
            logger.error(f"Error en monitoreo: {e}")

    async def resumen_suscripciones(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Envía cada 30 minutos el resumen de suscripciones a cada usuario"""
        try:
            materias = self.monitor.obtener_datos_siiau()
            for user_id, suscripciones_usuario in self.suscripciones.items():
                mensaje = "🕒 *Resumen de tus suscripciones (cada 30 minutos):*\n\n"
                for nrc, info in suscripciones_usuario.items():
                    materia = materias.get(str(nrc))
                    if materia:
                        status = "✅ Disponible" if materia.tiene_cupos() else "❌ Sin cupos"
                        mensaje += (
                            f"• *{materia.getNombre()}*\n"
                            f"  NRC: `{materia.getNRC()}` | {status}\n"
                            f"  Cupos: {materia.cupos_disponibles()}/{materia.cupos_totales()}\n"
                            f"  Profesor: {materia.getProfesor()}\n\n"
                        )
                    else:
                        mensaje += f"• NRC `{nrc}` no encontrado\n\n"
                
                mensaje += f"Actualizado: {datetime.now().strftime('%H:%M:%S')}"
                try:
                    await context.bot.send_message(chat_id=int(user_id), text=mensaje, parse_mode='Markdown')
                except Exception as e:
                    logger.error(f"Error enviando resumen a {user_id}: {e}")
        except Exception as e:
            logger.error(f"Error en resumen de suscripciones: {e}")

    async def unknown(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja comandos desconocidos"""
        await update.message.reply_text(
            "❌ Comando no reconocido.\nUsa `/ayuda` para ver los comandos disponibles.",
            parse_mode='Markdown'
        )

# Corrección: Pasar la instancia de application al shutdown handler
async def enviar_mensaje_cierre(application):
    """Envía mensaje cuando el bot se cierra correctamente"""
    admin_id = None
    global bot
    # Intentar obtener el ID del primer usuario en las suscripciones
    if bot.suscripciones:
        admin_id = next(iter(bot.suscripciones.keys()))

    if admin_id:
        try:
            await application.bot.send_message(
                chat_id=admin_id,
                text="❌ *Bot de monitoreo SIIAU ha cerrado sesión.*\n\n" \
                     "🔒 No estará disponible temporalmente.",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error enviando mensaje de cierre: {e}")

# Llamar al mensaje de cierre antes de detener el bot
import signal

def shutdown_handler(signum, frame):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(enviar_mensaje_cierre(application))
    logger.info("Bot detenido correctamente.")
    exit(0)

signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

# Definir application como global para acceso en el shutdown handler
global application

# Asegurar que la instancia de application esté disponible para el shutdown handler
def main():
    """
    Función principal que inicia el bot.
    
    Realiza las siguientes tareas:
    1. Lee el token del bot desde token.txt
    2. Configura los manejadores de comandos
    3. Configura los trabajos periódicos:
       - Monitoreo de cupos cada 10 segundos
       - Resumen de suscripciones cada 30 minutos
    4. Inicia el bot en modo polling
    
    Requisitos:
    - Archivo token.txt con el token del bot
    - Permisos de escritura para suscripciones.json
    """
    global application  # Declarar application como global
    try:
        # Leer el token del bot desde archivo
        with open('token.txt', 'r') as f:
            token = f.read().strip()
    except:
        logger.error("❌ No se pudo leer token.txt")
        return

    try:
        # Crear bot y aplicación
        application = ApplicationBuilder().token(token).build()
        bot = CuposBot()

        # Registrar handlers
        application.add_handler(CommandHandler('start', bot.start))
        application.add_handler(CommandHandler('ayuda', bot.ayuda))
        application.add_handler(CommandHandler('suscribir', bot.suscribir))
        application.add_handler(CommandHandler('desuscribir', bot.desuscribir))
        application.add_handler(CommandHandler('mis_suscripciones', bot.mis_suscripciones))
        application.add_handler(CommandHandler('verificar', bot.verificar))
        application.add_handler(CommandHandler('buscar', bot.buscar))
        application.add_handler(MessageHandler(filters.COMMAND, bot.unknown))

        # Configurar job para monitoreo
        job_queue = application.job_queue
        job_queue.run_repeating(bot.monitorear_cupos, interval=10, first=10)  # Actualiza cada 10 segundos
        job_queue.run_repeating(bot.resumen_suscripciones, interval=1800, first=30)  # Envía resumen cada 30 minutos

        # Función para enviar mensaje de inicio
        async def enviar_mensaje_inicio(context):
            """Envía mensaje cuando el bot inicia correctamente"""
            admin_id = None
            # Intentar obtener el ID del primer usuario en las suscripciones
            if bot.suscripciones:
                admin_id = next(iter(bot.suscripciones.keys()))

            if admin_id:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text="✅ *Bot de monitoreo SIIAU iniciado correctamente*\n\n" \
                             "🔄 Intervalo de monitoreo: 10 segundos\n" \
                             "📚 Ciclo: 202520 (fijo)",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Error enviando mensaje de inicio: {e}")

        # Agregar job para enviar mensaje de inicio (después de 5 segundos)
        job_queue.run_once(enviar_mensaje_inicio, when=5)

        # Iniciar bot
        logger.info("Bot iniciado. Presiona Ctrl+C para detener.")
        application.run_polling(drop_pending_updates=True)

    except Exception as e:
        logger.error(f"Error iniciando el bot: {e}")

if __name__ == '__main__':
    main()

"""
Bot de Monitoreo de Cupos SIIAU

Este bot de Telegram monitorea los cupos disponibles en materias del SIIAU (Sistema Integral de Información y Administración Universitaria)
de la Universidad de Guadalajara. Permite a los estudiantes suscribirse a materias específicas y recibir notificaciones cuando hay cupos disponibles.

Características principales:
- Monitoreo automático de cupos cada 10 segundos
- Notificaciones instantáneas cuando hay cupos disponibles
- Resumen de suscripciones cada 30 minutos
- Búsqueda de materias por nombre, NRC o clave
- Soporte para múltiples usuarios y suscripciones

Requisitos:
1. Python 3.7+
2. python-telegram-bot
3. Token de bot de Telegram (crear con @BotFather)

Configuración:
1. Crear un archivo token.txt con el token del bot de Telegram
2. Instalar dependencias: pip install python-telegram-bot
3. Ejecutar el script: python siiau_monitor_bot.py

Comandos disponibles:
/start - Iniciar el bot
/ayuda - Ver comandos disponibles
/suscribir [NRC] - Suscribirse a una materia
/desuscribir [NRC] - Desuscribirse de una materia
/mis_suscripciones - Ver materias suscritas
/verificar [NRC] - Verificar cupos de una materia
/buscar [término] - Buscar materias

Archivos necesarios:
- siiau_monitor_bot.py: Script principal
- database.py: Manejo de conexión con SIIAU
- token.txt: Token del bot de Telegram
- suscripciones.json: Almacenamiento de suscripciones (se crea automáticamente)

Nota: Este bot está configurado para el ciclo 202520 y la carrera ICOM por defecto.
Para modificar estos valores, editar la URL en la clase BaseDatos.

Autor: th3g3ntalm3n
Licencia: MIT
"""