# Bot Monitor de Cupos SIIAU 🤖

Un bot de Telegram que monitorea automáticamente la disponibilidad de cupos en materias del SIIAU (Sistema Integral de Información y Administración Universitaria) de la Universidad de Guadalajara. Notifica instantáneamente cuando hay cupos disponibles en las materias suscritas.

## Características ✨

- 🔄 Monitoreo automático cada 10 segundos
- 🔔 Notificaciones instantáneas cuando hay cupos
- 📊 Resumen de suscripciones cada 30 minutos
- 🔍 Búsqueda de materias por nombre, NRC o clave
- 👥 Soporte para múltiples usuarios
- 📱 Interfaz amigable a través de Telegram

## Requisitos Previos 📋

- Python 3.7 o superior
- python-telegram-bot
- Un token de bot de Telegram (obtenido a través de [@BotFather](https://t.me/botfather))
- Conexión a Internet

## Instalación 🛠️

1. Clona este repositorio:
```bash
git clone https://github.com/E1P3LON/SIIAUBot.git
cd SIIAUBot
```

2. Instala las dependencias usando requirements.txt:
```bash
pip install -r requirements.txt
```

3. Crea un archivo `token.txt` y agrega tu token de bot de Telegram:
```bash
echo "TU_TOKEN_AQUI" > token.txt
```

4. Modifica tu clave de carrera en `database.py` (por defecto está configurado para ICOM):
```python
url = "https://siiauescolar.siiau.udg.mx/wal/sspseca.consulta_oferta?ciclop=" + ciclo + "&cup=&majrp=ICOM&mostrarp=1000000"
```

## Uso 📱

1. Inicia el bot:
```bash
python siiau_monitor_bot.py
```

2. Busca tu bot en Telegram y comienza a usarlo con estos comandos:

- `/start` - Inicia el bot y muestra la ayuda
- `/ayuda` - Muestra todos los comandos disponibles
- `/suscribir [NRC]` - Suscríbete a una materia por su NRC
- `/desuscribir [NRC]` - Cancela la suscripción a una materia
- `/mis_suscripciones` - Ver tus materias suscritas
- `/verificar [NRC]` - Verifica cupos actuales de una materia
- `/buscar [término]` - Busca materias por nombre, NRC o clave

## Estructura del Proyecto 📁

- `siiau_monitor_bot.py` - Script principal del bot
- `database.py` - Manejo de conexión con SIIAU
- `token.txt` - Archivo con el token del bot (debes crearlo)
- `suscripciones.json` - Almacena las suscripciones (se crea automáticamente)
- `README.md` - Este archivo de documentación

## Funcionamiento 🔄

1. El bot se conecta a SIIAU cada 10 segundos para verificar cupos
2. Cuando encuentra cupos disponibles en una materia suscrita:
   - Envía una notificación inmediata al usuario
   - Incluye detalles como NRC, nombre, profesor y horario
3. Cada 30 minutos envía un resumen de todas las suscripciones
4. Usa emojis y formato Markdown para una mejor experiencia visual

## Personalización ⚙️

- Para cambiar el intervalo de monitoreo por cuanto tiempo quieres verificar los cupos, modifica el valor en `job_queue.run_repeating(bot.monitorear_cupos, interval=10)`
- Para cambiar el ciclo escolar, modifica `"202520"` en la clase `BaseDatos`
- Para cambiar la carrera, modifica `"ICOM"` en la URL de `BaseDatos`

## Autor ✒️

- **@E1P3LON** - *Trabajo inicial* - [@E1P3LON](https://github.com/E1P3LON)

## Licencia 📄

Este proyecto está bajo la Licencia MIT - mira el archivo [LICENSE](LICENSE) para detalles

