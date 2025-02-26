const express = require('express');
const fs = require('fs');
const https = require('https');
const bodyParser = require('body-parser');
const mysql = require('mysql2');

// Validación de parámetros
const args = process.argv.slice(2); // Ignorar los dos primeros argumentos (node y script)
if (args.length < 6) {
    console.error('Uso: node app.js <IP> <PORT> <HostBBDD> <user> <password> <database>');
    process.exit(1);
}

// Desestructuración de parámetros
const [IP, PORT, HostBBDD, user, password, database] = args;

// Crear una instancia de Express
const app = express();

// Configuración de conexión a MySQL
const conexion = mysql.createConnection({
    host: HostBBDD,
    user: user,
    password: password,
    database: database
});

// Conexión a la base de datos
conexion.connect(err => {
    if (err) {
        console.error('Error de conexión a la base de datos: ' + err.stack);
        process.exit(1);
    }
    console.log('Conexión exitosa con el id ' + conexion.threadId);
});

// Middleware para parsear el body de las peticiones como JSON
app.use(bodyParser.json());

// CRUD de taxis
// Función para crear un taxi
function crearTaxi(idTaxi) {
    idTaxi = idTaxi.toUpperCase();
    const query = 'INSERT INTO taxis (id) VALUES (?)';
    conexion.query(query, [idTaxi], (err, result) => {
        if (err) throw err;
        console.log(`Taxi '${idTaxi}' creado con éxito.`);
    });
}

// Función para eliminar un taxi
function eliminarTaxi(idTaxi) {
    idTaxi = idTaxi.toUpperCase();
    const query = 'DELETE FROM taxis WHERE id = ?';
    conexion.query(query, [idTaxi], (err, result) => {
        if (err) throw err;
        console.log(`Taxi '${idTaxi}' eliminado.`);
    });
}

// Alta de taxi
app.put('/register', (req, res) => {
    const { id } = req.body;
    if (!id) {
        return res.status(400).json({ message: 'ID de taxi requerido.' });
    }

    // Verificar si el taxi ya está registrado
    const query = 'SELECT * FROM taxis WHERE id = ?';
    conexion.query(query, [id], (err, result) => {
        if (err) return res.status(500).json({ message: 'Error al verificar el registro del taxi.' });

        if (result.length > 0) {
            return res.status(409).json({ message: 'Taxi ya registrado.' });
        }

        // Si no está registrado, lo creamos
        crearTaxi(id);
        res.status(201).json({ message: `Taxi ${id} registrado.` });
    });
});

// Baja de taxi
app.delete('/unregister/:id', (req, res) => {
    const { id } = req.params;

    // Verificar si el taxi está registrado
    const query = 'SELECT * FROM taxis WHERE id = ?';
    conexion.query(query, [id], (err, result) => {
        if (err) return res.status(500).json({ message: 'Error al verificar el registro del taxi.' });

        if (result.length === 0) {
            return res.status(404).json({ message: 'Taxi no encontrado.' });
        }

        // Si está registrado, lo eliminamos
        eliminarTaxi(id);
        res.status(200).json({ message: `Taxi ${id} eliminado.` });
    });
});

// Obtener todos los taxis registrados
app.get('/taxis', (req, res) => {
    const query = 'SELECT * FROM taxis';
    conexion.query(query, (err, result) => {
        if (err) return res.status(500).json({ message: 'Error al obtener los taxis.' });
        res.status(200).json(result);
    });
});

// Iniciar servidor HTTPS
const options = {
    key: fs.readFileSync('private.key'),
    cert: fs.readFileSync('certificate.crt')
};

https.createServer(options, app).listen(PORT, IP, () => {
    console.log(`EC_Registry está en ejecución en https://${IP}:${PORT}`);
});
