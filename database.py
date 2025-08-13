from html.parser import HTMLParser
from urllib import request
import ssl
from typing import List, Dict
from collections import defaultdict


class ParserUDG(HTMLParser):
    """Parser para extraer datos del HTML de SIIAU"""
    def __init__(self):
        super().__init__()
        self.reset_parser()
    def reset_parser(self):
        self.lastTag = ""
        self.lastClass = ""
        self.i = 0
        self.datos = []
    def handle_starttag(self, tag, attrs):
        self.lastTag = tag
        self.lastClass = ""
        for attr in attrs:
            if attr[0] == 'class':
                self.lastClass = attr[1]
        if tag == 'table':
            self.datos.append([])
            self.i = 0
            
    def handle_data(self, data):
        data = data.strip()
        if data and self.lastTag == 'td':
            if len(self.datos) > 0:
                if len(self.datos[-1]) <= self.i:
                    self.datos[-1].append(data)
                self.i += 1
                
    def feed_datos(self, html: str, datos: List) -> None:
        """Alimenta el parser con HTML y almacena los datos extraídos"""
        self.reset_parser()
        self.feed(html)
        if self.datos:
            datos.append(self.datos)

class BaseDatos:
    def __init__(self):
        import logging
        self.logger = logging.getLogger("BaseDatos")
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        # URL fija para ICOM
        url = "https://siiauescolar.siiau.udg.mx/wal/sspseca.consulta_oferta?ciclop=202520&cup=&majrp=ICOM&mostrarp=1000000"
        try:
            body = request.urlopen(url, context=ctx, timeout=30).read()
            body = body.decode('latin-1')
        except Exception as e:
            self.logger.error(f"Error al obtener datos de SIIAU: {e}")
            raise Exception(f"Error al obtener datos de SIIAU: {e}")

        Datos = []
        parser = ParserUDG()
        parser.feed_datos(str(body), Datos)

        if not Datos or not Datos[0]:
            self.logger.warning("No se obtuvieron datos de SIIAU")
            self.Datos = []
        else:
            self.Datos = Datos[0]

        self.NRCDict = {}
        self.ClaveDict = {}
        self.NombreDict = defaultdict(list)
        self.Clases = []
        for d in self.Datos:
            try:
                clase = Clase(d, self)
                self.Clases.append(clase)
                self.NRCDict[clase.getNRC()] = clase
                self.ClaveDict.setdefault(clase.getClave(), {})[clase.getNRC()] = clase
                self.NombreDict[clase.getNombre().lower()].append(clase)
            except Exception as e:
                self.logger.error(f"Error procesando clase: {e}")

        # Malla curricular ICOM
        # Aqui modifica la lista a tu malla
        self.malla = {
            'primero': ["I5288", "I5247", "IG738", "IL340", "IL342", "IL341"],
            'segundo': ["IL352", "IL345", "IL344", "IL345", "IL353", "LT251"],
            'tercero': ["I5289", "IB056", "IL347", "IL346", "IL363", "IL349"],
            'cuarto': ["IL354", "IB067", "IL348", "IL365", "IL362", "IL350"],
            'quinto': ["IL355", "IL356", "IL366", "IL361", "IL364", "IL369"],
            'sexto': ["IL351", "IL367", "CB224", "IL358"],
            'septimo': ["IL357", "IL370", "IL372"],
            'octavo': ["IL359", "IL368", "IL373"],
            'noveno': ["IL360", "IL371", "IL374"],
            'optativas': ["IL378","IL379","IL380","IL381","IL382","IL383"],
            'todo': list(self.ClaveDict.keys())
        }

    def findNRC(self, nrc):
        """Busca una clase por NRC"""
        if isinstance(nrc, list):
            return [self.findNRC(i) for i in nrc]
        return self.NRCDict.get(str(nrc))

    def findClave(self, clave):
        """Busca clases por clave de materia"""
        if isinstance(clave, list):
            result = []
            for c in clave:
                if c in self.ClaveDict:
                    result.extend(list(self.ClaveDict[c].values()))
            return result
        return list(self.ClaveDict.get(clave, {}).values())

    def findNombre(self, nombre):
        """Busca clases por nombre (case-insensitive)"""
        nombre = nombre.lower()
        return self.NombreDict.get(nombre, [])

    def findNested(self, code):
        """Búsqueda anidada por código (NRC, clave, nombre o semestre)"""
        if isinstance(code, list):
            return [self.findNested(i) for i in code]
        if code in self.malla:
            return self.find(self.malla[code])
        elif Clase.isClave(code):
            return self.findClave(code)
        elif code.isdigit():
            return self.findNRC(code)
        else:
            return self.findNombre(code)

    def find(self, code):
        """Método general de búsqueda"""
        result = self.findNested(code)
        # Aplanar resultados anidados
        if isinstance(result, list):
            flat_result = []
            for item in result:
                if isinstance(item, list):
                    flat_result.extend(item)
                elif item is not None:
                    flat_result.append(item)
            return flat_result
        return result if result is not None else []

class Clase:
    """Representa una clase con su información detallada"""
    def __init__(self, datos, base_datos):
        self.datos = datos  # Datos crudos de la clase
        self.BaseDeDatos = base_datos  # Referencia a la base de datos
        self._procesar_datos()

    def _procesar_datos(self):
        if not isinstance(self.datos, list) or len(self.datos) < 8:
            raise ValueError("Datos insuficientes para crear la clase")
        self.centro = str(self.datos[0])
        self.nrc = str(self.datos[1])
        self.clave = str(self.datos[2])
        self.nombre = str(self.datos[3])
        self.seccion = str(self.datos[4])
        self.creditos = str(self.datos[5])
        self.cupos = str(self.datos[6])
        self.disponibles = str(self.datos[7])
        self.horarios = []
        if len(self.datos) > 8 and isinstance(self.datos[8], list):
            self.horarios = self.datos[8]
        self.profesores = []
        if len(self.datos) > 9 and isinstance(self.datos[9], list):
            self.profesores = self.datos[9]

    def getClave(self) -> str:
        return self.clave

    def getNRC(self) -> str:
        return self.nrc

    def getProfesor(self, index: int = 0) -> str:
        if 0 <= index < len(self.profesores):
            return self.profesores[index][1] if isinstance(self.profesores[index], list) else self.profesores[index]
        return ""

    @staticmethod
    def isClave(codigo: str) -> bool:
        return isinstance(codigo, str) and codigo.upper().startswith('I')

"""
Instrucciones para subir este archivo como parte de un proyecto en GitHub:

1. Asegúrate de que este archivo esté en el directorio raíz de tu proyecto.
2. Inicializa un repositorio de Git en el directorio del proyecto si aún no lo has hecho:
   git init
3. Agrega este archivo al área de preparación:
   git add database.py
4. Realiza un commit con un mensaje descriptivo:
   git commit -m "Agregar archivo de base de datos para el bot de monitoreo SIIAU"
5. Si aún no tienes un repositorio remoto, crea uno en GitHub.
6. Vincula tu repositorio local con el remoto:
   git remote add origin <URL-del-repositorio>
7. Sube los cambios al repositorio remoto:
   git push -u origin main

Nota: Asegúrate de no subir información sensible al repositorio público. Usa un archivo `.gitignore` para excluirlos si es necesario.
"""
