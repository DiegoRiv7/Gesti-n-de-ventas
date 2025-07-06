# cartera_clientes/app/urls.py

from django.urls import path
from . import views # Importa las vistas desde el mismo directorio de la aplicación

urlpatterns = [
    # Ruta para la página de inicio del dashboard
    path("", views.home, name="home"),
    
    # Ruta para la lista de todas las oportunidades de venta (o las del usuario)
    path("todos/", views.todos, name="todos"),
    
    # Rutas para ingresar nuevas oportunidades de venta
    path("ingresar-venta/", views.ingresar_venta_todoitem, name="ingresar_venta_todoitem"),
    path("ingresar-venta-exitosa/", views.ingresar_venta_todoitem_exitosa, name="ingresar_venta_todoitem_exitosa"),
    
    # Rutas de autenticación (registro, login, logout)
    path("register/", views.register, name="register"),
    path("login/", views.user_login, name="user_login"),
    path("logout/", views.user_logout, name="user_logout"),
    
    # Ruta para editar o eliminar una oportunidad de venta específica
    # <int:pk> captura el ID numérico de la oportunidad
    path("editar-venta/<int:pk>/", views.editar_venta_todoitem, name="editar_venta_todoitem"),
    
    # Ruta para el reporte de ventas por cliente
    path("reporte-clientes/", views.reporte_ventas_por_cliente, name="reporte_ventas_por_cliente"),
    
    # Ruta para ver las oportunidades de un cliente específico
    # <int:cliente_id> captura el ID numérico del cliente
    path("oportunidades-cliente/<int:cliente_id>/", views.oportunidades_por_cliente, name="oportunidades_por_cliente"),
    
    # Ruta para el detalle del dashboard por producto
    # <str:producto_val> captura el valor del producto (ej. "PRODUCTO_A")
    path("producto-detalle/<str:producto_val>/", views.producto_dashboard_detail, name="producto_dashboard_detail"),
    
    # Ruta para el detalle del dashboard por mes de cierre
    # <str:mes_val> captura el valor del mes (ej. "07" para Julio)
    path("mes-detalle/<str:mes_val>/", views.mes_dashboard_detail, name="mes_dashboard_detail"),

    # Ruta para el detalle de oportunidades perdidas (0% probabilidad)
    path("oportunidades-perdidas/", views.oportunidades_perdidas_detail, name="oportunidades_perdidas_detail"),
]

