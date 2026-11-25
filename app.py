#Este es el archivo que hace arrancar todo lo demas, aqui se ejecuta todo

import argparse
import os
import webbrowser

from servidor_web import AplicacionSIGE, iniciar_servidor

#Esta funcion es la funcion main, o alias la funcion que llama a todo el resto de archivos para que el progrma empieze a funcionar 
def main():
    parser = argparse.ArgumentParser(description="SIGE - Gestión de estacionamientos")
    parser.add_argument("--puerto", type=int, default=8765)
    parser.add_argument("--sin-navegador", action="store_true")
    argumentos = parser.parse_args()

    carpeta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos")
    primera_vez = not os.path.exists(os.path.join(carpeta, "estacionamientos.csv"))
    app = AplicacionSIGE(carpeta)
    servidor = iniciar_servidor(app, argumentos.puerto)
    url = f"http://127.0.0.1:{servidor.server_address[1]}"

    print("=" * 62)
    print("SIGE - Gestión de estacionamientos")
    print("=" * 62)
    print("Primera ejecución: se crearon los datos de demostración." if primera_vez
          else f"Datos recuperados desde {carpeta}")
    print(f"Aplicación abierta en:  {url}")
    print(f"Excel con los datos:    {app.repo.ruta_excel}")
    if app.repo.estado_excel["estado"] == "SIN_OPENPYXL":
        print("AVISO: falta instalar openpyxl para generar el Excel. Ejecuta:  pip install openpyxl")
    print("Para cerrar la aplicación presiona Ctrl+C en esta ventana.")
    if not argumentos.sin_navegador:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nAplicación cerrada. Los datos quedaron guardados.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
