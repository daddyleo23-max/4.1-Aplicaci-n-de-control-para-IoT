"""Entrega022: cierre funcional y documentación; no incluye secretos ni respaldos."""
from pathlib import Path
import runpy
import zipfile
from empaquetar_inventario_prueba import build_backend


def main():
    root=Path(__file__).resolve().parents[1]
    runpy.run_path(str(root/'tools/empaquetar_frontend_prueba.py'),run_name='__main__')
    backend=build_backend(root)
    target=root.parent/'entrega_022_cierre_4_3.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        for name in ('019_control_empresa.up.sql','020_catalogo_resumen.up.sql'):
            z.write(root/'sql/migrations'/name,name)
        for name in ('migrar_copia_rds.py','respaldar_rds.py','probar_admin_http.py',
                     'probar_control_empresa_sql.py','probar_cierre_4_3_http.py',
                     'probar_demos_empresa_http.py','probar_capacidades_http.py',
                     'probar_control_http.py','probar_invitados_http.py','probar_soporte_operativo_http.py'):
            z.write(root/'tools'/name,name)
        with zipfile.ZipFile(backend) as source:
            for name in source.namelist():z.writestr('backend/'+name,source.read(name))
        z.write(root.parent/'frontend_4_3_prueba.zip','frontend_4_3_prueba.zip')
        for path in sorted((root/'docs').rglob('*')):
            if path.is_file():z.write(path,'documentacion/'+path.relative_to(root/'docs').as_posix())
        z.writestr('LEEME.txt','''ENTREGA022 — cierre funcional 4.3. Extraer en C:\\entrega_022.
Requiere copia con migraciones001–018. NO aplicar al esquema original.
Instrucciones completas: documentacion/despliegue-4.3.md.
1. Liberar todas las reservas; detener backend8001 y frontend8080.
2. Desde C:\\practica_2_6_iot respaldar la COPIA con respaldar_rds.py --copia.
3. Aplicar SQL019 y SQL020 EN ORDEN con migrar_copia_rds.py de esta entrega.
   Piden admin/contraseña SQL de RDS. Ante error conservar informe, no repetir.
4. Ejecutar probar_control_empresa_sql.py --copia; usa ROLLBACK.
5. Copiar CONTENIDO backend/ a C:\\practica_4_3_pruebas y reiniciar como antes.
6. Ejecutar probar_cierre_4_3_http.py desde C:\\practica_2_6_iot.
   Pide correo/contraseña ADMINISTRADOR DE LA APLICACIÓN.
7. Al aprobar, actualizar frontend con frontend_4_3_prueba.zip y Ctrl+F5.
Empresa también ADQUIERE CONTROL antes de movimientos o demos; no cambia
la prioridad DETENER ni da soporte sin consentimiento a unidades vendidas.
El catálogo añade capacidades y un asset genérico; no se añade imagen al mando.
Dashboard: demos EMPRESA activas, disponibilidad real y resumen de inventario.
Listas: búsqueda/páginas y selectores sin truncar a100. Admin: ADMINISTRACIÓN.
Login: HTTP429 con espera hasta60s si se repite demasiadas veces. Pruebas HTTP
secuenciales: no ejecutar varias suites a la vez.
Regresiones incluidas son versiones actualizadas para reservas de empresa.
Comprobado LOCALMENTE (MariaDB), pendiente MySQL8.4/RDS real y publicación.
No hay firmware nuevo ni publicación automática; no confirma movimiento físico.
ZIP frontend apunta a localhost8001: NO subirlo a GitHub Pages.
''')
    print(target)


if __name__=='__main__':main()
