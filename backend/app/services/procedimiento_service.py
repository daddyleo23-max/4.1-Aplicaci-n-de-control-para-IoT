
from app.database import get_connection


class ProcedimientoService:

    def ejecutar_consulta_transaccional(self, procedimiento, parametros=(), precondiciones=()):
        """Persistir una operación que también devuelve un resultado."""
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                for guardia, argumentos in precondiciones:
                    cursor.execute(f"CALL {guardia}({', '.join(['%s'] * len(argumentos))})", argumentos)
                    while cursor.nextset():
                        pass
                consulta = f"CALL {procedimiento}({', '.join(['%s'] * len(parametros))})"
                cursor.execute(consulta, parametros)
                resultados = cursor.fetchall()
                while cursor.nextset():
                    pass
            connection.commit()
            return resultados
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def ejecutar_consulta(self, procedimiento, parametros=()):
        connection = None

        try:
            connection = get_connection()

            with connection.cursor() as cursor:
                consulta = (
                    f"CALL {procedimiento}"
                    f"({', '.join(['%s'] * len(parametros))})"
                )
                cursor.execute(consulta, parametros)

                resultados = cursor.fetchall()

                while cursor.nextset():
                    pass

                return resultados

        finally:
            if connection:
                connection.close()

    def ejecutar_transaccion(self, operaciones):
        connection = None

        try:
            connection = get_connection()

            with connection.cursor() as cursor:
                for procedimiento, parametros in operaciones:
                    consulta = (
                        f"CALL {procedimiento}"
                        f"({', '.join(['%s'] * len(parametros))})"
                    )

                    cursor.execute(consulta, parametros)

                    # Consumir todos los resultados del procedimiento.
                    while cursor.nextset():
                        pass

            connection.commit()

        except Exception:
            if connection:
                connection.rollback()
            raise

        finally:
            if connection:
                connection.close()
