
# **EasyCab - Sistemas Distribuidos 24/25** 🚖  
**Práctica 2 - Seguridad y API Rest**  

## 📌 Descripción  
EasyCab es un sistema distribuido para la gestión de taxis en una ciudad. Esta versión incluye mejoras en seguridad, autenticación y comunicación mediante API REST. Se han implementado las siguientes características:  
- **Autenticación de taxis** mediante un sistema de **tokens**.  
- **Cifrado** de las comunicaciones entre los taxis y el servidor central utilizando **RSA y Fernet**.  
- **Integración con la API de OpenWeather** para determinar si el clima es adecuado para la circulación.  
- **Uso de Kafka** para la comunicación entre los diferentes módulos del sistema.  
- **Base de datos** para almacenar información sobre los taxis registrados y autenticados.  

## 📂 Estructura del Proyecto  

📦 EasyCab
 ┣ 📂 central
 ┃ ┣ 📜 EC_Central.py
 ┃ ┣ 📜 api_central.py
 ┣ 📂 customer
 ┃ ┣ 📜 EC_Customer.py
 ┣ 📂 taxi_de
 ┃ ┣ 📜 EC_DE.py
 ┣ 📂 sensor
 ┃ ┣ 📜 EC_S.py
 ┣ 📂 registry
 ┃ ┣ 📜 EC_Registry.js
 ┣ 📂 CTC
 ┃ ┣ 📜 EC_CTC.js
 ┣ 📜 README.md
 ┣ 📜 requirements.txt
 

## ⚙️ Instalación y Configuración  
### 📌 Requisitos previos  
Antes de ejecutar el sistema, asegúrate de tener instalado:  
- **Python 3**  
- **Node.js y npm**  
- **Kafka** ([Descargar](https://kafka.apache.org/downloads))  
- **Librerías necesarias**:  

  pip install kafka-python colorama tabulate cryptography mysql-connector-python flask-cors flask
  npm install express https body-parser


### 🚀 Despliegue  
1. **Iniciar Kafka**  

   cd PATH_KAFKA/kafka  
   bin/zookeeper-server-start.sh config/zookeeper.properties  
   bin/kafka-server-start.sh config/server.properties  

2. **Ejecutar los módulos**  
 
   python3 api_central.py <IP_Central> <puerto API central> <IP_CTC> <puerto CTC>  
   python3 EC_Central.py <IP_Kafka> <puerto Kafka>  
   node EC_Registry.js <IP_Registry> <puerto Registry>  
   python3 EC_DE.py <IP_Central> <puerto Central> <ID_Taxi>  


## 📌 Funcionamiento  
- Al iniciar el sistema, los **taxis pueden autenticarse** y recibir tokens.  
- La API de OpenWeather determina si los taxis pueden circular.  
- Si la temperatura es menor o igual a 0°C, los taxis **vuelven a base y se desautentican** automáticamente.  
- Los clientes pueden solicitar taxis, y estos responderán si están disponibles.  

## 🔒 Seguridad  
- **Autenticación con tokens** generados en EC_Central.  
- **Cifrado asimétrico (RSA)** para compartir claves simétricas.  
- **Cifrado simétrico (Fernet)** para la comunicación de datos sensibles.  
- **Canal seguro HTTPS y SSL** en el registro de taxis.  

## 📜 Autores  
- **José Javier Vega Sarabia**  
- **Álvaro Ferrándiz García**  
 

