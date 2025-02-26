const readline = require('readline');
const axios = require('axios');

// Validación de parámetros de entrada
const args = process.argv.slice(2); // Ignorar los dos primeros argumentos (node y script)
if (args.length < 2) {
    console.error('Uso: node app.js <IP_Registry> <Port_registry>');
    process.exit(1);
}

// Asignar los parámetros
const [IP_Registry, Port_registry] = args;

// Crear una interfaz para la entrada de consola
const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
});

// Función para registrar un taxi
const registrarTaxi = async (id) => {
    try {
        const response = await axios.put(`https://${IP_Registry}:${Port_registry}/register`, 
            { id }, 
            { httpsAgent: new (require('https').Agent)({ rejectUnauthorized: false }) }
        );
        console.log(response.data.message);
    } catch (error) {
        if (error.response) {
            console.log(`Error: ${error.response.data.message}`);
        } else {
            console.log(`Error de conexión: ${error.message}`);
        }
    }
};

// Función para dar de baja un taxi
const darDeBajaTaxi = async (id) => {
    try {
        const response = await axios.delete(`https://${IP_Registry}:${Port_registry}/unregister/${id}`, 
            { httpsAgent: new (require('https').Agent)({ rejectUnauthorized: false }) }
        );
        console.log(response.data.message);
    } catch (error) {
        if (error.response) {
            console.log(`Error: ${error.response.data.message}`);
        } else {
            console.log(`Error de conexión: ${error.message}`);
        }
    }
};

// Función para mostrar el menú y gestionar opciones
const mostrarMenu = () => {
    console.log("\n=== Menú de EC_Registry ===");
    console.log("1. Dar de alta un taxi");
    console.log("2. Dar de baja un taxi");
    console.log("3. Salir");
    rl.question("Seleccione una opción: ", async (opcion) => {
        switch (opcion) {
            case '1':
                rl.question("Ingrese el ID del taxi para dar de alta: ", async (id) => {
                    await registrarTaxi(id);
                    mostrarMenu();
                });
                break;
            case '2':
                rl.question("Ingrese el ID del taxi para dar de baja: ", async (id) => {
                    await darDeBajaTaxi(id);
                    mostrarMenu();
                });
                break;
            case '3':
                console.log("Saliendo del menú...");
                rl.close();
                break;
            default:
                console.log("Opción no válida.");
                mostrarMenu();
                break;
        }
    });
};

// Iniciar el menú
mostrarMenu();
