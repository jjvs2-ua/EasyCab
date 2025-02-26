const express = require('express');
const axios = require('axios');
const readline = require('readline');
const fs = require('fs');
const path = require('path');

// Verificar que se proporcionen todos los parámetros necesarios
if (process.argv.length < 6) {
    console.error("Uso: node app.js <IP> <PORT> <apikey.txt> <City>");
    process.exit(1);
}

const HOST = process.argv[2]; // Host
const PORT = parseInt(process.argv[3], 10); // Puerto
const API_KEY_FILE = process.argv[4]; // Archivo de API key
const CIUDAD_INICIAL = process.argv[5]; // Ciudad inicial

const app = express();

// Leer la API key desde el archivo especificado
let API_KEY = '';
try {
    API_KEY = fs.readFileSync(path.join(__dirname, API_KEY_FILE), 'utf8').trim();
    if (!API_KEY) {
        throw new Error('API key está vacía');
    }
} catch (error) {
    console.error(`Error al leer ${API_KEY_FILE}: ${error.message}`);
    console.error('Por favor, verifique el archivo de API key');
    process.exit(1);
}

const BASE_URL = 'http://api.openweathermap.org/data/2.5/weather';

let ciudadActual = CIUDAD_INICIAL; // Ciudad inicial

// Función para obtener el clima
async function obtenerClima(ciudad) {
    try {
        const respuesta = await axios.get(BASE_URL, {
            params: {
                q: ciudad,
                appid: API_KEY,
                units: 'metric' // Unidades en grados Celsius
            }
        });
        return respuesta.data;
    } catch (error) {
        console.error(`Error al obtener el clima: ${error.message}`);
        return null;
    }
}

// Ruta principal del API
app.get('/clima', async (req, res) => {
    //console.log(`Consulta recibida para la ciudad: ${ciudadActual}`);
    const clima = await obtenerClima(ciudadActual);

    if (!clima) {
        return res.status(500).json({
            status: 'KO',
            message: 'Error al obtener datos del clima'
        });
    }

    try {
        const temperatura = clima.main.temp;
        const estado = temperatura < 0 ? 'KO' : 'OK';

        //console.log(`DEBUG -> Ciudad: ${ciudadActual}, Temperatura: ${temperatura}°C, Estado: ${estado}`);

        return res.status(200).json({
            status: estado,
            temperatura,
            ciudad: ciudadActual
        });
    } catch (error) {
        console.error(`Error al procesar datos del clima: ${error.message}`);
        return res.status(500).json({
            status: 'KO',
            message: 'Datos incompletos del API'
        });
    }
});

// Función para manejar el menú interactivo
function iniciarMenu() {
    const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout
    });

    const mostrarMenu = () => {
        console.log("\nMenú EC_CTC:");
        console.log("1. Ver ciudad actual");
        console.log("2. Cambiar ciudad");
        console.log("3. Salir");
        rl.question("Seleccione una opción: ", async (opcion) => {
            switch (opcion) {
                case "1":
                    console.log(`Ciudad actual: ${ciudadActual}`);
                    break;
                case "2":
                    rl.question("Ingrese el nombre de la nueva ciudad: ", (nuevaCiudad) => {
                        ciudadActual = nuevaCiudad;
                        console.log(`Ciudad cambiada a: ${ciudadActual}`);
                        mostrarMenu(); // Volver al menú
                    });
                    return; // Salir para evitar mostrar el menú dos veces
                case "3":
                    console.log("Saliendo del menú...");
                    rl.close();
                    process.exit(0); // Termina el proceso
                default:
                    console.log("Opción no válida. Intente de nuevo.");
            }
            mostrarMenu();
        });
    };

    mostrarMenu();
}

// Iniciar el servidor REST en un hilo independiente
function iniciarServidor() {
    app.listen(PORT, HOST, () => {
        console.log(`EC_CTC escuchando en ${HOST}:${PORT}...`);
        console.log(`EC_CTC corriendo en http://${HOST}:${PORT}/clima`);
    });
}

// Iniciar tanto el menú como el servidor
iniciarServidor();
iniciarMenu();
