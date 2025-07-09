from django.shortcuts import render, HttpResponse, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import TodoItem, Cliente, Cotizacion, DetalleCotizacion # Asegúrate de importar los nuevos modelos
from .forms import VentaForm, VentaFilterForm, CotizacionForm # Asegúrate de que CotizacionForm esté importado
from django.db.models import Sum, Count, F, Q
from django.db.models.functions import Upper, Coalesce
from django.db.models import Value
from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal # Importa Decimal para manejar números con precisión
from django.utils.html import json_script
import json
from django.http import JsonResponse
from django.urls import reverse # Importar reverse para construir URLs
from django.utils import timezone

# Importaciones para generación de PDF
from weasyprint import HTML
from django.template.loader import render_to_string
from django.http import HttpResponse

# Asegúrate de importar tu modelo Cotizacion y DetalleCotizacion
from .models import Cotizacion, DetalleCotizacion

# Importaciones para el logo Base64 (asegúrate de que estas líneas estén al inicio del archivo si no lo están)
import base64
import os

# Función auxiliar para comprobar si el usuario es supervisor
def is_supervisor(user):
    return user.groups.filter(name='Supervisores').exists()

# Función auxiliar para obtener el display de un valor de choice
def _get_display_for_value(value, choices_list):
    return dict(choices_list).get(value, value)

# Vistas principales y funcionales
@login_required
def bienvenida(request):
    """
    Vista de bienvenida que será la primera que vea el usuario al ingresar.
    """
    # Determinar perfil
    perfil = "SUPERVISOR" if is_supervisor(request.user) else "VENDEDOR"
    # Fecha actual
    fecha_actual = timezone.localtime(timezone.now()).strftime('%A, %d de %B de %Y')

    # Usuario del mes: más ventas cerradas (probabilidad 100%) este mes, solo vendedores
    inicio_mes = date.today().replace(day=1)
    fin_mes = date.today()
    ventas_mes = (
        TodoItem.objects.filter(probabilidad_cierre=100, fecha_creacion__date__gte=inicio_mes, fecha_creacion__date__lte=fin_mes)
        .exclude(usuario__groups__name='Supervisores')
        .values('usuario')
        .annotate(ventas_cerradas=Count('id'))
        .order_by('-ventas_cerradas')
    )
    usuario_mes = None
    monto_vendido_mes = 0
    if ventas_mes:
        user_id = ventas_mes[0]['usuario']
        user = User.objects.get(id=user_id)
        # Calcular el monto total vendido por este usuario en el mes actual (probabilidad 100%)
        monto_vendido_mes = TodoItem.objects.filter(
            probabilidad_cierre=100,
            fecha_creacion__date__gte=inicio_mes,
            fecha_creacion__date__lte=fin_mes,
            usuario=user
        ).aggregate(total=Sum('monto'))['total'] or 0
        usuario_mes = {
            'nombre': user.get_full_name() or user.username,
            'avatar_url': f'https://ui-avatars.com/api/?name={user.get_full_name() or user.username}&background=38bdf8&color=fff',
            'ventas_cerradas': ventas_mes[0]['ventas_cerradas'],
            'monto_vendido_mes': monto_vendido_mes,
        }

    # Usuario del día: más oportunidades registradas hoy, solo vendedores
    hoy = date.today()
    oportunidades_hoy = (
        TodoItem.objects.filter(fecha_creacion__date=hoy)
        .exclude(usuario__groups__name='Supervisores')
        .values('usuario')
        .annotate(oportunidades_hoy=Count('id'))
        .order_by('-oportunidades_hoy')
    )
    usuario_dia = None
    if oportunidades_hoy:
        user_id = oportunidades_hoy[0]['usuario']
        user = User.objects.get(id=user_id)
        usuario_dia = {
            'nombre': user.get_full_name() or user.username,
            'avatar_url': f'https://ui-avatars.com/api/?name={user.get_full_name() or user.username}&background=f472b6&color=fff',
            'oportunidades_hoy': oportunidades_hoy[0]['oportunidades_hoy'],
        }

    # Últimas oportunidades (de todos)
    ultimas_oportunidades_qs = TodoItem.objects.select_related('cliente', 'usuario').order_by('-fecha_creacion')[:8]
    ultimas_oportunidades = [
        {
            'nombre': o.oportunidad,
            'cliente': o.cliente.nombre_empresa if o.cliente else '',
            'monto': o.monto,
            'probabilidad': o.probabilidad_cierre,
            'fecha_creacion': o.fecha_creacion,
        }
        for o in ultimas_oportunidades_qs
    ]

    # Clima: dejar None, preparado para integración futura
    clima = None

    context = {
        'perfil': perfil,
        'fecha_actual': fecha_actual,
        'usuario_mes': usuario_mes,
        'usuario_dia': usuario_dia,
        'ultimas_oportunidades': ultimas_oportunidades,
        'clima': clima,
    }
    return render(request, 'bienvenida.html', context)

@login_required
def dashboard(request):
    # Determinar si el usuario es un supervisor
    if is_supervisor(request.user):
        # Si es supervisor, obtiene todas las oportunidades de todos los usuarios
        user_opportunities = TodoItem.objects.all()
        print("DEBUG: Usuario es supervisor. Obteniendo todas las oportunidades.")
    else:
        # Si no es supervisor, solo obtiene las oportunidades del usuario actual
        user_opportunities = TodoItem.objects.filter(usuario=request.user)
        print(f"DEBUG: Usuario {request.user.username} es vendedor. Obteniendo sus propias oportunidades.")

    # 1. Cliente con más/menos ventas cerradas (100% probabilidad)
    # Las ventas cerradas se filtran por usuario si no es supervisor
    ventas_cerradas_query = TodoItem.objects.filter(probabilidad_cierre=100, cliente__isnull=False)
    if not is_supervisor(request.user):
        ventas_cerradas_query = ventas_cerradas_query.filter(usuario=request.user)

    cliente_mas_vendido = None
    cliente_menos_vendido = None

    ventas_por_cliente_cerradas = ventas_cerradas_query.values('cliente__nombre_empresa', 'cliente__id').annotate( # Asegura cliente__id
        total_vendido=Sum('monto')
    ).order_by('-total_vendido')

    if ventas_por_cliente_cerradas.exists():
        cliente_mas_vendido = ventas_por_cliente_cerradas.first()
        cliente_menos_vendido = ventas_por_cliente_cerradas.last()

    # 2. Producto más/menos vendido (total de oportunidades y ventas cerradas)
    # La consulta de productos también debe considerar el rol de supervisor
    productos_data_base_query = TodoItem.objects.all() if is_supervisor(request.user) else TodoItem.objects.filter(usuario=request.user)

    productos_data_raw = productos_data_base_query.annotate(
        # Convertir el campo 'producto' a mayúsculas para la agrupación
        producto_upper=Upper('producto')
    ).values('producto_upper').annotate(
        count_oportunidades=Count('id'),
        total_monto=Sum('monto'),
        # Suma el monto SOLO si la probabilidad de cierre es 100%
        total_vendido_cerrado=Sum('monto', filter=Q(probabilidad_cierre=100))
    ).order_by('-count_oportunidades') # Ordenar para encontrar el "más vendido"

    productos_data_with_display = []
    for item in productos_data_raw:
        item_copy = item.copy()
        # Usa 'producto_upper' para obtener el display, ya que es el valor normalizado
        item_copy['get_producto_display'] = _get_display_for_value(item_copy['producto_upper'], TodoItem.PRODUCTO_CHOICES)
        # Asegúrate de que total_vendido_cerrado sea 0.00 si es None
        item_copy['total_vendido_cerrado'] = item_copy['total_vendido_cerrado'] or Decimal('0.00')
        productos_data_with_display.append(item_copy)

    productos_data_sorted_asc = sorted(productos_data_with_display, key=lambda x: x['count_oportunidades'])
    productos_data_sorted_desc = sorted(productos_data_with_display, key=lambda x: x['count_oportunidades'], reverse=True)

    # Inicializar producto_mas_vendido y producto_menos_vendido
    producto_mas_vendido = None
    producto_menos_vendido = None

    # Asignar valores después de ordenar las listas
    if productos_data_sorted_desc:
        producto_mas_vendido = productos_data_sorted_desc[0]
    if productos_data_sorted_asc:
        producto_menos_vendido = productos_data_sorted_asc[0]


    # Si producto_mas_vendido existe, aseguramos que la clave 'producto' en el contexto sea la versión UPPER
    if producto_mas_vendido:
        producto_mas_vendido_context = {
            'producto': producto_mas_vendido['producto_upper'], # Usamos producto_upper para la URL
            'get_producto_display': producto_mas_vendido['get_producto_display'],
            'count_oportunidades': producto_mas_vendido['count_oportunidades'],
            'total_vendido_cerrado': producto_mas_vendido['total_vendido_cerrado'],
        }
    else:
        producto_mas_vendido_context = None

    # Si producto_menos_vendido existe, aseguramos que la clave 'producto' en el contexto sea la versión UPPER
    if producto_menos_vendido:
        producto_menos_vendido_context = {
            'producto': producto_menos_vendido['producto_upper'], # Usamos producto_upper para la URL
            'get_producto_display': producto_menos_vendido['get_producto_display'],
            'count_oportunidades': producto_menos_vendido['count_oportunidades'],
            'total_vendido_cerrado': producto_menos_vendido['total_vendido_cerrado'],
        }
    else:
        producto_menos_vendido_context = None


    # --- Lógica para el Próximo Mes y Alerta de Meta ---
    # Obtener el próximo mes
    today = date.today()
    next_month_date = today + relativedelta(months=1)
    next_month_value = next_month_date.month # El valor numérico del mes

    # Obtener el nombre del próximo mes para la visualización
    next_month_display = dict(TodoItem.MES_CHOICES).get(str(next_month_value).zfill(2), f"Mes {next_month_value}")

    # Obtener las oportunidades del próximo mes (considerando el rol)
    oportunidades_proximo_mes_query = TodoItem.objects.filter(mes_cierre=str(next_month_value).zfill(2))
    if not is_supervisor(request.user):
        oportunidades_proximo_mes_query = oportunidades_proximo_mes_query.filter(usuario=request.user)

    total_oportunidades_proximo_mes = oportunidades_proximo_mes_query.count()
    total_monto_esperado_proximo_mes = oportunidades_proximo_mes_query.aggregate(sum_monto=Sum('monto'))['sum_monto'] or Decimal('0.00')


    # Lógica para la alerta de meta
    META_MENSUAL = Decimal('130000.00') # Convertir a Decimal
    total_ponderado_proximo_mes = Decimal('0.00') # Inicializar como Decimal

    for op in oportunidades_proximo_mes_query: # Iterar sobre el queryset filtrado
        if 70 <= op.probabilidad_cierre <= 100:
            total_ponderado_proximo_mes += op.monto * Decimal('1.00') # Alta importancia
        elif 50 <= op.probabilidad_cierre <= 69:
            total_ponderado_proximo_mes += op.monto * Decimal('0.50') # Media importancia
        else: # op.probabilidad_cierre < 50
            total_ponderado_proximo_mes += op.monto * Decimal('0.10') # Baja importancia

    alerta_proximo_mes = {
        'status': '',
        'message': '',
        'icon': ''
    }

    if total_ponderado_proximo_mes >= META_MENSUAL:
        alerta_proximo_mes['status'] = 'success'
        alerta_proximo_mes['message'] = '¡Meta mensual alcanzada o superada!'
        alerta_proximo_mes['icon'] = 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' # Checkmark circle
    elif total_ponderado_proximo_mes >= META_MENSUAL * Decimal('0.70'): # Multiplicar por Decimal
        alerta_proximo_mes['status'] = 'warning'
        alerta_proximo_mes['message'] = 'Cerca de la meta, aún es posible alcanzarla.'
        alerta_proximo_mes['icon'] = 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z' # Exclamation triangle
    else:
        alerta_proximo_mes['status'] = 'danger'
        alerta_proximo_mes['message'] = 'Se requiere más esfuerzo para alcanzar la meta.'
        alerta_proximo_mes['icon'] = 'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z' # X-mark circle


    # --- TOTAL PERDIDO (0% probabilidad) ---
    oportunidades_perdidas_query = TodoItem.objects.filter(probabilidad_cierre=0)
    if not is_supervisor(request.user):
        oportunidades_perdidas_query = oportunidades_perdidas_query.filter(usuario=request.user)

    total_perdido_monto = oportunidades_perdidas_query.aggregate(
        sum_monto=Sum('monto')
    )['sum_monto'] or Decimal('0.00') # Asegurar que sea Decimal
    total_perdido_count = oportunidades_perdidas_query.count()


    context = {
        'cliente_mas_vendido': cliente_mas_vendido,
        'cliente_menos_vendido': cliente_menos_vendido,
        'producto_mas_vendido': producto_mas_vendido_context, # Usamos el nuevo contexto
        'producto_menos_vendido': producto_menos_vendido_context, # Usamos el nuevo contexto para menos vendido

        # Datos del próximo mes
        'next_month_display': next_month_display,
        'total_oportunidades_proximo_mes': total_oportunidades_proximo_mes,
        'total_monto_esperado_proximo_mes': total_monto_esperado_proximo_mes,
        'alerta_proximo_mes': alerta_proximo_mes,
        'proximo_mes_val': str(next_month_value).zfill(2),

        # Total Perdido
        'total_perdido_monto': total_perdido_monto,
        'total_perdido_count': total_perdido_count,
        'is_supervisor': is_supervisor(request.user), # Pasamos si el usuario es supervisor al contexto
    }
    return render (request, "dashboard.html", context)


@login_required
def get_user_clients_api(request):
    """
    Vista API que devuelve los clientes asignados al usuario autenticado.
    Si el usuario es supervisor, devuelve todos los clientes.
    """
    try:
        if is_supervisor(request.user):
            # Si el usuario es supervisor, obtener todos los clientes
            clients_queryset = Cliente.objects.all()
            print("DEBUG: Usuario es supervisor. Obteniendo todos los clientes.")
        else:
            # Si no es supervisor, obtener solo los clientes asignados a este usuario
            # Usamos 'asignado_a' que es el campo correcto en tu modelo Cliente
            clients_queryset = Cliente.objects.filter(asignado_a=request.user)
            print(f"DEBUG: Usuario {request.user.username} es vendedor. Obteniendo sus clientes.")

        # Serializar los clientes a un formato que pueda ser convertido a JSON
        clients_data = []
        for client in clients_queryset:
            clients_data.append({
                'id': str(client.id), # Convertir ID a string para consistencia con JSON
                'name': client.nombre_empresa, # Mapear nombre_empresa a 'name'
                'address': client.direccion, # Mapear direccion a 'address'
                'taxId': client.email # Mapear email a 'taxId' (o el campo que uses para ID Fiscal)
                # Puedes añadir más campos aquí si los necesitas en el frontend
            })
        return JsonResponse(clients_data, safe=False) # safe=False permite serializar listas directamente
    except Exception as e:
        print(f"ERROR en get_user_clients_api: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def todos (request):
    # Determinar si el usuario es un supervisor
    if is_supervisor(request.user):
        items = TodoItem.objects.all()
    else:
        items = TodoItem.objects.filter(usuario=request.user)

    filter_form = VentaFilterForm(request.GET)

    if filter_form.is_valid():
        area = filter_form.cleaned_data.get('area')
        producto = filter_form.cleaned_data.get('producto')
        orden_monto = filter_form.cleaned_data.get('orden_monto')
        probabilidad_min = filter_form.cleaned_data.get('probabilidad_min')
        probabilidad_max = filter_form.cleaned_data.get('probabilidad_max')
        mes_cierre = filter_form.cleaned_data.get('mes_cierre')

        if area:
            items = items.filter(area=area)
        if producto:
            # Modificación aquí: hacer la búsqueda del producto insensible a mayúsculas/minúsculas
            items = items.filter(producto__iexact=producto) # Usa icontains o iexact para insensibilidad
        if probabilidad_min is not None:
            items = items.filter(probabilidad_cierre__gte=probabilidad_min)
        if probabilidad_max is not None:
            items = items.filter(probabilidad_cierre__lte=probabilidad_max)
        if mes_cierre:
            items = items.filter(mes_cierre=mes_cierre)

        if orden_monto:
            if orden_monto == 'monto_asc':
                items = items.order_by('monto')
            elif orden_monto == 'monto_desc':
                items = items.order_by('-monto')
        else:
            items = items.order_by('-fecha_creacion')
    else:
        items = items.order_by('-fecha_creacion')

    print(f"DEBUG: Total items en vista 'todos' después de filtros: {items.count()}")
    for item in items:
        print(f"DEBUG:    - ID: {item.id}, Oportunidad: {item.oportunidad}, Producto: {item.producto}, Usuario ID: {item.usuario.id}")


    context = {
        "items":items,
        "filter_form": filter_form,
        "is_supervisor": is_supervisor(request.user), # También pasamos esto al template de "todos"
    }
    return render (request, "todos.html", context)

@login_required
def ingresar_venta_todoitem(request):
    # Permitir a supervisores y vendedores ingresar ventas
    if request.method == 'POST':
        if is_supervisor(request.user):
            form = VentaForm(request.POST)
        else:
            form = VentaForm(request.POST, user=request.user)
        if form.is_valid():
            venta = form.save(commit=False)
            # Si es supervisor, toma el usuario del formulario
            if is_supervisor(request.user):
                venta.usuario = form.cleaned_data['usuario']
            else:
                venta.usuario = request.user
            venta.save()
            return redirect('ingresar_venta_todoitem_exitosa')
        else:
            # Si el formulario no es válido, mostrar errores y mantener datos
            return render(request, 'ingresar_venta.html', {'form': form, 'errores': form.errors})
    else:
        if is_supervisor(request.user):
            form = VentaForm()
        else:
            form = VentaForm(user=request.user)
    return render(request, 'ingresar_venta.html', {'form': form})

def ingresar_venta_todoitem_exitosa(request):
    return render(request, 'ingresar_venta_exitosa.html')

# Vistas de autenticación
def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home') # Redirigir a 'home' después de registrar e iniciar sesión
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})

def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home') # Redirigir a 'home' después de iniciar sesión
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form, 'hide_dock': True}) # Pasar hide_dock=True para ocultar el dock

@login_required
def user_logout(request):
    logout(request)
    return redirect('user_login')

@login_required
def editar_venta_todoitem(request, pk):
    # Supervisor puede editar cualquier venta, vendedor solo las suyas
    if is_supervisor(request.user):
        todo_item = get_object_or_404(TodoItem, pk=pk) # No filtrar por usuario si es supervisor
    else:
        todo_item = get_object_or_404(TodoItem, pk=pk, usuario=request.user)

    if request.method == 'POST':
        if 'delete' in request.POST:
            todo_item.delete()
            return redirect('todos')

        # Al guardar, si es supervisor, el form no necesita el 'user' para el queryset de Cliente
        form = VentaForm(request.POST, instance=todo_item, user=request.user if not is_supervisor(request.user) else None) # Asegúrate de que usa VentaForm
        if form.is_valid():
            form.save()
            return redirect('todos')
    else:
        form = VentaForm(instance=todo_item, user=request.user if not is_supervisor(request.user) else None) # Asegúrate de que usa VentaForm

    return render(request, 'editar_venta.html', {'form': form, 'todo_item': todo_item})


@login_required
def reporte_ventas_por_cliente(request):
    if is_supervisor(request.user):
        # Si es supervisor, obtener TODOS los clientes y el monto vendido (probabilidad 100%)
        # Sumamos oportunidades con prob_cierre=100 y usamos Coalesce para 0.00 si no hay ventas
        reporte_data = Cliente.objects.annotate(
            total_monto=Coalesce(
                Sum('oportunidades__monto', filter=Q(oportunidades__probabilidad_cierre=100)),
                Value(Decimal('0.00')) # Asegura que si no hay ventas, el monto sea 0.00
            )
        ).values(
            'id', # Para la URL
            'nombre_empresa', # Para mostrar el nombre del cliente
            'total_monto' # El monto calculado
        ).order_by('nombre_empresa')

        # Para el total general del supervisor, sumamos todas las ventas cerradas del sistema
        total_general = TodoItem.objects.filter(probabilidad_cierre=100).aggregate(
            sum_monto=Sum('monto')
        )['sum_monto'] or Decimal('0.00')

    else:
        # Para vendedores: obtener solo los clientes asignados a este vendedor
        # y el monto vendido (probabilidad 100%), mostrando 0.00 si no hay ventas cerradas
        reporte_data = Cliente.objects.filter(asignado_a=request.user).annotate(
            total_monto=Coalesce(
                Sum('oportunidades__monto', filter=Q(oportunidades__probabilidad_cierre=100, oportunidades__usuario=request.user)),
                Value(Decimal('0.00')) # Asegura 0.00 si no hay ventas para ESTE VENDEDOR
            )
        ).values(
            'id', # Para la URL
            'nombre_empresa', # Para mostrar el nombre del cliente
            'total_monto' # El monto calculado
        ).order_by('nombre_empresa')

        # Para el total general del vendedor, sumamos solo sus ventas cerradas
        total_general = TodoItem.objects.filter(
            usuario=request.user, probabilidad_cierre=100
        ).aggregate(sum_monto=Sum('monto'))['sum_monto'] or Decimal('0.00')


    context = {
        'reporte_data': reporte_data,
        'total_general': total_general,
        'is_supervisor': is_supervisor(request.user),
    }
    return render(request, 'reporte_ventas_por_cliente.html', context)


@login_required
def oportunidades_por_cliente(request, cliente_id):
    # Determinar qué clientes pueden ser vistos por el usuario
    if is_supervisor(request.user):
        cliente_seleccionado = get_object_or_404(Cliente, pk=cliente_id) # No filtrar por usuario
        oportunidades = TodoItem.objects.filter(cliente=cliente_seleccionado) # Todas las oportunidades del cliente
        print("DEBUG: Supervisor viendo oportunidades de cliente.")
    else:
        cliente_seleccionado = get_object_or_404(Cliente, pk=cliente_id, asignado_a=request.user) # Usar asignado_a
        oportunidades = TodoItem.objects.filter(cliente=cliente_seleccionado, usuario=request.user)
        print(f"DEBUG: Vendedor {request.user.username} viendo sus propias oportunidades de cliente.")

    # El formulario de filtro no necesita el usuario para sus querysets de clientes en este contexto
    # ya que los clientes ya vienen filtrados por la vista o se obtienen todos.
    filter_form = VentaFilterForm(request.GET)

    if filter_form.is_valid():
        area = filter_form.cleaned_data.get('area')
        producto = filter_form.cleaned_data.get('producto')
        orden_monto = filter_form.cleaned_data.get('orden_monto')
        probabilidad_min = filter_form.cleaned_data.get('probabilidad_min')
        probabilidad_max = filter_form.cleaned_data.get('probabilidad_max')
        mes_cierre = filter_form.cleaned_data.get('mes_cierre')

        if area:
            oportunidades = oportunidades.filter(area=area)
        if producto:
            oportunidades = oportunidades.filter(producto=producto)
        if probabilidad_min is not None:
            oportunidades = oportunidades.filter(probabilidad_cierre__gte=probabilidad_min)
        if probabilidad_max is not None:
            oportunidades = oportunidades.filter(probabilidad_cierre__lte=probabilidad_max)
        if mes_cierre:
            oportunidades = oportunidades.filter(mes_cierre=mes_cierre)

        if orden_monto:
            if orden_monto == 'monto_asc':
                oportunidades = oportunidades.order_by('monto')
            elif orden_monto == 'monto_desc':
                oportunidades = oportunidades.order_by('-monto')
        else:
            oportunidades = oportunidades.order_by('-fecha_creacion')
    else:
        oportunidades = oportunidades.order_by('-fecha_creacion')


    context = {
        'cliente': cliente_seleccionado,
        'oportunidades': oportunidades,
        'filter_form': filter_form,
        'is_supervisor': is_supervisor(request.user),
    }
    return render(request, 'oportunidades_por_cliente.html', context)


@login_required
def producto_dashboard_detail(request, producto_val):
    print(f"DEBUG: producto_dashboard_detail - producto_val recibido RAW: {producto_val}")

    # Convertir a mayúsculas para asegurar que la comparación con PRODUCTO_CHOICES sea consistente
    producto_val_upper = producto_val.upper()
    print(f"DEBUG: producto_dashboard_detail - producto_val_upper: {producto_val_upper}")
    print(f"DEBUG: Keys de PRODUCTO_CHOICES: {list(dict(TodoItem.PRODUCTO_CHOICES).keys())}")

    # Verificar si el producto_val_upper es una clave válida en PRODUCTO_CHOICES
    if producto_val_upper not in dict(TodoItem.PRODUCTO_CHOICES).keys():
        print(f"DEBUG: Redirigiendo a home porque '{producto_val_upper}' no es una clave válida en PRODUCTO_CHOICES.")
        return redirect('home') # Redirige a home si el producto no es válido

    # Filtrar oportunidades por el producto (usando iexact para insensibilidad a mayúsculas/minúsculas)
    # y por usuario si no es supervisor
    oportunidades_producto_query = TodoItem.objects.filter(producto__iexact=producto_val_upper)
    if not is_supervisor(request.user):
        oportunidades_producto_query = oportunidades_producto_query.filter(usuario=request.user)

    print(f"DEBUG: Oportunidades encontradas para {producto_val_upper} (antes de desglosar): {oportunidades_producto_query.count()}")
    for op in oportunidades_producto_query:
        print(f"DEBUG:   - ID: {op.id}, Oportunidad: {op.oportunidad}, Producto: {op.producto}, Usuario ID: {op.usuario.id}")


    # --- Ventas Cerradas (probabilidad 100%) para este producto ---
    ventas_cerradas = oportunidades_producto_query.filter(probabilidad_cierre=100)
    total_vendido_cerrado = ventas_cerradas.aggregate(sum_monto=Sum('monto'))['sum_monto'] or Decimal('0.00')
    total_vendido_cerrado_count = ventas_cerradas.count() # Conteo de oportunidades cerradas
    print(f"DEBUG: Ventas Cerradas (100%) para '{producto_val_upper}': {total_vendido_cerrado_count} oportunidades, Monto: {total_vendido_cerrado}")
    for venta in ventas_cerradas:
        print(f"DEBUG:   - Oportunidad: {venta.oportunidad}, Monto: {venta.monto}, Probabilidad: {venta.probabilidad_cierre}%")


    # --- Oportunidades Vigentes (probabilidad del 1% al 99%) para este producto ---
    oportunidades_vigentes = oportunidades_producto_query.filter(
        probabilidad_cierre__gt=0, # Mayor que 0%
        probabilidad_cierre__lt=100 # Menor que 100%
    )
    total_monto_vigente = oportunidades_vigentes.aggregate(sum_monto=Sum('monto'))['sum_monto'] or Decimal('0.00')
    total_monto_vigente_count = oportunidades_vigentes.count() # Conteo de oportunidades vigentes
    print(f"DEBUG: Oportunidades Vigentes (0% < prob < 100%) para '{producto_val_upper}': {total_monto_vigente_count} oportunidades, Monto: {total_monto_vigente}")
    for op_vigente in oportunidades_vigentes:
        print(f"DEBUG:   - Oportunidad: {op_vigente.oportunidad}, Monto: {op_vigente.monto}, Probabilidad: {op_vigente.probabilidad_cierre}%")

    # --- Oportunidades Perdidas (probabilidad 0%) para este producto ---
    oportunidades_perdidas = oportunidades_producto_query.filter(probabilidad_cierre=0)
    total_monto_perdido = oportunidades_perdidas.aggregate(sum_monto=Sum('monto'))['sum_monto'] or Decimal('0.00')
    total_monto_perdido_count = oportunidades_perdidas.count() # Conteo de oportunidades perdidas
    print(f"DEBUG: Oportunidades Perdidas (0%) para '{producto_val_upper}': {total_monto_perdido_count} oportunidades, Monto: {total_monto_perdido}")
    for op_perdida in oportunidades_perdidas:
        print(f"DEBUG:   - Oportunidad: {op_perdida.oportunidad}, Monto: {op_perdida.monto}, Probabilidad: {op_perdida.probabilidad_cierre}%")


    # Clientes involucrados en este producto
    clientes_involucrados = oportunidades_producto_query.filter(cliente__isnull=False).values('cliente__id', 'cliente__nombre_empresa').distinct()

    # Meses involucrados en este producto (mes de cierre esperado)
    meses_involucrados = oportunidades_producto_query.values('mes_cierre').distinct()

    # Mapear valores crudos de mes a sus nombres de visualización
    meses_display = []
    for m in meses_involucrados:
        # Aseguramos que la clave sea un string de dos dígitos para la búsqueda
        mes_key = str(m['mes_cierre']).zfill(2)
        meses_display.append(dict(TodoItem.MES_CHOICES).get(mes_key, mes_key))
    context = {
        'producto_val': producto_val_upper, # Aseguramos que la clave pasada sea la que usará el template
        'producto_display': dict(TodoItem.PRODUCTO_CHOICES).get(producto_val_upper, producto_val_upper),
        'total_vendido_cerrado': total_vendido_cerrado,
        'total_vendido_cerrado_count': total_vendido_cerrado_count, # AÑADIDO
        'total_monto_vigente': total_monto_vigente, # Nuevo: Monto oportunidades vigentes
        'total_monto_vigente_count': total_monto_vigente_count, # AÑADIDO
        'total_monto_perdido': total_monto_perdido, # Nuevo: Monto oportunidades perdidas
        'total_monto_perdido_count': total_monto_perdido_count, # AÑADIDO
        'clientes_involucrados': clientes_involucrados,
        'meses_involucrados_display': meses_display,
        'oportunidades': oportunidades_producto_query, # Pasar todas las oportunidades para listarlas
        'is_supervisor': is_supervisor(request.user), # Pasamos si el usuario es supervisor al contexto
    }
    return render(request, 'producto_dashboard_detail.html', context)


@login_required
def mes_dashboard_detail(request, mes_val):
    # Asegúrate de que el mes_val recibido es uno de los choices válidos
    mes_val_padded = str(mes_val).zfill(2) # Asegurar que mes_val sea de dos dígitos para la validación
    if mes_val_padded not in dict(TodoItem.MES_CHOICES).keys():
        return redirect('home') # Redirige a home si el mes no es válido

    # Base queryset de oportunidades según el rol
    if is_supervisor(request.user):
        oportunidades_mes = TodoItem.objects.filter(mes_cierre=mes_val_padded)
    else:
        oportunidades_mes = TodoItem.objects.filter(usuario=request.user, mes_cierre=mes_val_padded)


    # Monto total esperado para este mes
    total_monto_esperado = oportunidades_mes.aggregate(sum_monto=Sum('monto'))['sum_monto'] or Decimal('0.00')

    # Clientes involucrados en oportunidades para este mes
    clientes_involucrados = oportunidades_mes.filter(cliente__isnull=False).values('cliente__id', 'cliente__nombre_empresa').distinct()

    # Datos para la gráfica: Probabilidad de cierre vs. Monto
    graph_data_raw = oportunidades_mes.values('id', 'oportunidad', 'producto', 'monto', 'probabilidad_cierre', 'cliente__nombre_empresa')

    # Añadir 'get_producto_display' a cada item en graph_data
    graph_data_with_display = []
    for item in graph_data_raw:
        item_copy = item.copy()
        item_copy['get_producto_display'] = dict(TodoItem.PRODUCTO_CHOICES).get(item_copy['producto'], item_copy['producto'])
        graph_data_with_display.append(item_copy)

    context = {
        'mes_val': mes_val_padded, # Aseguramos que la clave pasada sea la que usará el template
        'mes_display': dict(TodoItem.MES_CHOICES).get(mes_val_padded, mes_val_padded),
        'total_monto_esperado': total_monto_esperado,
        'clientes_involucrados': clientes_involucrados,
        'oportunidades': oportunidades_mes, # Pasar todas las oportunidades para listarlas
        'graph_data_json': graph_data_with_display, # Pasa los datos procesados con display_value
        'is_supervisor': is_supervisor(request.user),
    }
    return render(request, 'mes_dashboard_detail.html', context)


@login_required
def oportunidades_perdidas_detail(request):
    """
    Vista para mostrar todas las oportunidades con 0% de probabilidad de cierre.
    Considera el rol de supervisor.
    """
    if is_supervisor(request.user):
        oportunidades_perdidas = TodoItem.objects.filter(probabilidad_cierre=0).order_by('-fecha_creacion')
    else:
        oportunidades_perdidas = TodoItem.objects.filter(usuario=request.user, probabilidad_cierre=0).order_by('-fecha_creacion')

    total_perdido_monto = oportunidades_perdidas.aggregate(
        sum_monto=Sum('monto')
    )['sum_monto'] or Decimal('0.00')

    context = {
        'oportunidades': oportunidades_perdidas,
        'titulo': "Oportunidades Perdidas (0% Probabilidad)",
        'total_perdido_monto': total_perdido_monto,
        'is_supervisor': is_supervisor(request.user),
    }
    return render(request, 'oportunidades_perdidas_detail.html', context)


# VISTA DEPRECADA - MANTENIDA POR REFERENCIA
@login_required
def generate_quote_pdf(request, pk):
    """
    DEPRECATED: Esta vista generaba PDF para TodoItem.
    Now it will use generate_cotizacion_pdf for the Cotizacion model.
    """
    # Ensure that only the owner or a supervisor can generate the quote
    if is_supervisor(request.user):
        opportunity = get_object_or_404(TodoItem, pk=pk)
    else:
        opportunity = get_object_or_404(TodoItem, pk=pk, usuario=request.user)

    # Context for the PDF template
    context = {
        'opportunity': opportunity,
        'request_user': request.user, # To show the user generating the quote
        'current_date': date.today(),
        # You can add more company data here if you have it in the model or settings
        'company_name': 'Tu Empresa de Ventas S.A. de C.V.',
        'company_address': 'Calle Ficticia #123, Colonia Ejemplo, Ciudad de México',
        'company_phone': '+52 55 1234 5678',
        'company_email': 'ventas@tuempresa.com',
    }

    # Render the HTML template to a string
    html_string = render_to_string('quote_pdf.html', context)

    # Create the PDF from the HTML string
    # You can add a base_url if you have external images or CSS that WeasyPrint needs to load
    # Example: HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf(...)
    pdf_file = HTML(string=html_string).write_pdf()

    # Create the HTTP response with the PDF
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="cotizacion_{opportunity.oportunidad}.pdf"'
    return response


# This view seems to be duplicated in your original code.
# If you have two functions with the same name 'editar_venta_todoitem',
# Django will use the last one defined. It is recommended to have only one.
# I have kept it as it was in your original file.
@login_required
def editar_venta_todoitem(request, pk):
    # Get the TodoItem (opportunity) instance to edit by its primary key (pk)
    # If not found, returns a 404 error.
    oportunidad = get_object_or_404(TodoItem, pk=pk)

    if request.method == 'POST':
        # If the request is POST, it means the user has submitted the form with changes.
        # Instantiate the VentaForm with the submitted data (request.POST)
        # and, crucially, with the existing opportunity instance (instance=oportunidad).
        # We also pass the current user (request.user) to the form.
        form = VentaForm(request.POST, instance=oportunidad, user=request.user)
        if form.is_valid():
            form.save()
            # Redirect the user to the 'todos' page (where the opportunities table is listed)
            # after successful editing.
            return redirect('todos')
    else:
        # If the request is GET, the user is asking to view the edit form.
        # Instantiate the VentaForm with the existing opportunity instance.
        # We also pass the current user (request.user) to the form.
        # This preloads all form fields with the current opportunity values,
        # allowing the user to view and modify existing data.
        form = VentaForm(instance=oportunidad, user=request.user)

    # Render the 'ingresar_venta.html' template.
    # This template is used for both creating new sales and editing them,
    # as the form (VentaForm) is the same.
    # The form (preloaded or empty) and the opportunity instance (useful for the template) are passed.
    return render(request, 'ingresar_venta.html', {'form': form, 'oportunidad': oportunidad})


# --- NEW/CORRECTED VIEWS ADDED ---

@login_required
def oportunidades_por_cliente_view(request, cliente_id):
    """
    View to display sales opportunities for a specific client.
    """
    cliente = get_object_or_404(Cliente, pk=cliente_id)

    if is_supervisor(request.user):
        oportunidades = TodoItem.objects.filter(cliente=cliente).order_by('-fecha_creacion')
    else:
        oportunidades = TodoItem.objects.filter(cliente=cliente, usuario=request.user).order_by('-fecha_creacion')

    context = {
        'cliente_id': cliente_id,
        'cliente_nombre': cliente.nombre_empresa, # Use nombre_empresa
        'oportunidades': oportunidades,
    }
    return render(request, 'oportunidades_por_cliente.html', context)


@login_required
def crear_cotizacion_view(request, cliente_id=None):
    """
    View to create a new quote.
    Handles the creation of the quote and its product details,
    then returns a JSON response with the PDF URL.
    """
    cliente_seleccionado = None
    if cliente_id:
        cliente_seleccionado = get_object_or_404(Cliente, pk=cliente_id)

    if request.method == 'POST':
        # Instantiate the form with POST data
        form = CotizacionForm(request.POST)

        if form.is_valid():
            cotizacion = form.save(commit=False)
            cotizacion.save()
            print(f"DEBUG: Quote saved with ID: {cotizacion.id}")

            # Collect product data sent from JavaScript
            productos_data = {}
            # Iterate through request.POST.items() to correctly parse product data
            # The keys will look like 'productos[1][nombre]', 'productos[1][cantidad]', etc.
            # We need to group them by index.
            for key, value in request.POST.items():
                if key.startswith('productos['):
                    # Extract the index and the field name
                    # Example: 'productos[1][nombre]' -> index '1', field 'nombre'
                    parts = key.split('[')
                    index = parts[1].split(']')[0]
                    field = parts[2].split(']')[0]

                    if index not in productos_data:
                        productos_data[index] = {}
                    productos_data[index][field] = value

            # Convert the dictionary of dictionaries into a list of dictionaries,
            # sorted by their original numerical index to maintain order.
            productos_list = [productos_data[key] for key in sorted(productos_data.keys(), key=int)]
            print(f"DEBUG: productos_list before saving details: {productos_list}") # NEW DEBUG PRINT FOR DUPLICATION ISSUE

            # Calculate subtotal and quote totals
            calculated_subtotal = Decimal('0.00')
            for item_data in productos_list:
                try:
                    cantidad = int(item_data.get('cantidad', 0))
                    precio = Decimal(item_data.get('precio', '0.00'))
                    descuento = Decimal(item_data.get('descuento', '0.00'))
                    
                    item_total = cantidad * precio
                    item_total -= item_total * (descuento / Decimal('100.00'))
                    calculated_subtotal += item_total.quantize(Decimal('0.01')) # Round each item to 2 decimal places before summing
                    print(f"DEBUG_CALC: Item: {item_data.get('nombre')}, Quantity: {cantidad}, Price: {precio}, Discount: {descuento}, Item Total (rounded): {item_total.quantize(Decimal('0.01'))}")
                except (ValueError, TypeError) as e:
                    print(f"Warning: Invalid product data found: {item_data} - Error: {e}")
                    # Consider returning an error here or logging more severely
                    # If a detail is invalid, it's better to delete the entire quote
                    cotizacion.delete()
                    return JsonResponse({'success': False, 'errors': {'__all__': [{'message': f'Invalid product data in row. Error: {e}'}]}}, status=400)

            # Round the subtotal before calculating IVA
            cotizacion.subtotal = calculated_subtotal.quantize(Decimal('0.01'))
            
            try:
                cotizacion.iva_rate = Decimal(request.POST.get('iva_rate', '0.00'))
            except (ValueError, TypeError):
                cotizacion.iva_rate = Decimal('0.00') # Default to 0 if conversion fails

            cotizacion.iva_amount = (cotizacion.subtotal * cotizacion.iva_rate).quantize(Decimal('0.01')) # Round IVA amount
            cotizacion.total = (cotizacion.subtotal + cotizacion.iva_amount).quantize(Decimal('0.01')) # Round final total
            
            cotizacion.tipo_cotizacion = request.POST.get('tipo_cotizacion') # Use tipo_cotizacion
            cotizacion.created_by = request.user  # Asigna el usuario creador
            cotizacion.save(update_fields=['subtotal', 'iva_rate', 'iva_amount', 'total', 'tipo_cotizacion', 'created_by']) # Incluye created_by
            print(f"DEBUG: Quote totals updated. Subtotal: {cotizacion.subtotal}, IVA: {cotizacion.iva_amount}, Total: {cotizacion.total}, Quote Type: {cotizacion.tipo_cotizacion}")
            

            # Save product details after the quote has been saved and its totals calculated
            for item_data in productos_list:
                try:
                    DetalleCotizacion.objects.create(
                        cotizacion=cotizacion,
                        nombre_producto=item_data.get('nombre', ''),
                        descripcion=item_data.get('descripcion', ''),
                        cantidad=int(item_data.get('cantidad', 1)),
                        precio_unitario=Decimal(item_data.get('precio', '0.00')),
                        descuento_porcentaje=Decimal(item_data.get('descuento', '0.00'))
                    )
                    print(f"DEBUG: Product detail created: {item_data.get('nombre')}")
                except (ValueError, TypeError) as e:
                    print(f"Error saving DetalleCotizacion: {e} for data {item_data}")
                    # If a detail fails, it's better to delete the entire quote
                    cotizacion.delete() # Revert the quote if details are invalid
                    return JsonResponse({'success': False, 'errors': {'__all__': [{'message': f'Error saving product details. Error: {e}'}]}}, status=400)

            
            pdf_url = reverse('generate_cotizacion_pdf', args=[cotizacion.id])
            print(f"DEBUG: PDF URL generated: {pdf_url}")
            
            return JsonResponse({'success': True, 'pdf_url': pdf_url})

        else:
            # If the form is not valid, return a JSON response with errors
            errors_dict = {}
            for field, field_errors in form.errors.items():
                errors_dict[field] = [{'message': str(e), 'code': e.code if hasattr(e, 'code') else 'invalid'} for e in field_errors]
            print(f"DEBUG: Form errors: {errors_dict}")
            return JsonResponse({'success': False, 'errors': errors_dict}, status=400)

    else: # If the request is GET
        form = CotizacionForm() # Create an empty form for GET requests

    # Get clients for the frontend selector, filtering by user if not supervisor
    if is_supervisor(request.user):
        clientes_queryset = Cliente.objects.all()
    else:
        clientes_queryset = Cliente.objects.filter(asignado_a=request.user)

    # Use .values() to get dictionaries and map field names
    clientes_para_frontend = clientes_queryset.values(
        'id', 'nombre_empresa', 'direccion', 'email'
    )

    # Convert the QuerySet to a list of dictionaries with the field names expected by the frontend
    clientes_data_json = []
    for c in clientes_para_frontend:
        clientes_data_json.append({
            'id': str(c['id']),
            'name': c['nombre_empresa'],
            'address': c['direccion'],
            'taxId': c['email'] # Or the field you use for Tax ID
        })

    context = {
        'form': form,
        'cliente_seleccionado': cliente_seleccionado, # Pass the client object if it comes from the URL
        'clientes_data_json': json.dumps(clientes_data_json), # Pass the JSON of clients for JS
        'cliente_id_inicial': cliente_id, # Pass the initial ID for JS to pre-select
    }
    return render(request, 'crear_cotizacion.html', context)


@login_required
def generate_cotizacion_pdf(request, cotizacion_id):
    """
    View to generate the PDF of a specific quote.
    """
    print(f"DEBUG: Starting generate_cotizacion_pdf for quote ID: {cotizacion_id}")
    cotizacion = get_object_or_404(Cotizacion, pk=cotizacion_id)
    print(f"DEBUG: Quote found: {cotizacion.id} - Quote Type: {cotizacion.tipo_cotizacion}")
    
    # Ensure that the user has permission to view this quote
    if not is_supervisor(request.user) and cotizacion.created_by != request.user:
        print(f"DEBUG: Access denied for user {request.user.username} to quote {cotizacion.id}")
        return HttpResponse("Access denied.", status=403)

    detalles_cotizacion = DetalleCotizacion.objects.filter(cotizacion=cotizacion)
    print(f"DEBUG: Quote details found: {detalles_cotizacion.count()}")

    # Calculate IVA as a percentage to display in the PDF
    # cotizacion.iva_rate is already the decimal value (e.g., 0.08 or 0.16)
    iva_rate_percentage = (cotizacion.iva_rate * Decimal('100')).quantize(Decimal('1'))
    print(f"DEBUG: IVA rate: {iva_rate_percentage}%")

    # --- Get the name for the PDF ---
    pdf_name_raw = ""
    if hasattr(cotizacion, 'nombre_cotizacion') and cotizacion.nombre_cotizacion:
        pdf_name_raw = cotizacion.nombre_cotizacion
    elif hasattr(cotizacion, 'titulo') and cotizacion.titulo:
        pdf_name_raw = cotizacion.titulo
    else:
        pdf_name_raw = f"Cotizacion_{cotizacion.id}"

    pdf_name = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in pdf_name_raw).strip()
    pdf_name = pdf_name.replace(' ', '_')

    if not pdf_name:
        pdf_name = f"Cotizacion_{cotizacion.id}"
    print(f"DEBUG: PDF file name: {pdf_name}.pdf")

    # --- Logic to handle logo and company information based on quote type ---
    tipo_cotizacion = cotizacion.tipo_cotizacion 
    logo_base64 = ""
    company_name = ""
    company_address = ""
    company_phone = ""
    company_email = ""
    template_name = 'cotizacion_pdf_template.html' # Default template

    if tipo_cotizacion == 'Bajanet':
        try:
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'img', 'bajanet_logo.png')
            with open(logo_path, "rb") as image_file:
                logo_base64 = base64.b64encode(image_file.read()).decode('utf-8')
            print(f"DEBUG: BAJANET logo loaded from: {logo_path}")
        except FileNotFoundError:
            print(f"Warning: BAJANET logo not found in {logo_path}")
            logo_base64 = ""
        company_name = 'BAJANET S.A. de C.V.'
        company_address = 'Calle Ficticia #123, Colonia Ejemplo, Ciudad de México'
        company_phone = '+52 55 1234 5678'
        company_email = 'ventas@bajanet.com'
        template_name = 'cotizacion_pdf_template.html'
    elif tipo_cotizacion == 'Iamet':
        logo_base64 = "" 
        company_name = 'IAMET S.A. de C.V.'
        company_address = 'Av. Principal #456, Col. Centro, Guadalajara, Jalisco'
        company_phone = '+52 33 9876 5432'
        company_email = 'contacto@iamet.com'
        template_name = 'iamet_cotizacion_pdf_template.html'
        print(f"DEBUG: Configuration for IAMET. Using template: {template_name}")
    else:
        print(f"DEBUG: Unknown or null quote type: '{tipo_cotizacion}'. Using default configuration.")
        logo_base64 = ""
        company_name = 'Tu Empresa de Ventas S.A. de C.V.'
        company_address = 'Calle Ficticia #123, Colonia Ejemplo, Ciudad de México'
        company_phone = '+52 55 1234 5678'
        company_email = 'ventas@tuempresa.com'
        template_name = 'cotizacion_pdf_template.html'

    context = {
        'cotizacion': cotizacion,
        'detalles_cotizacion': detalles_cotizacion,
        'request_user': request.user,
        'current_date': date.today(),
        'company_name': company_name,
        'company_address': company_address,
        'company_phone': company_phone,
        'company_email': company_email,
        'logo_base64': logo_base64,
        'iva_rate_percentage': iva_rate_percentage,
    }

    try:
        print(f"DEBUG: Attempting to render template: {template_name}")
        html_string = render_to_string(template_name, context)
        print("DEBUG: Template rendered to HTML string.")
    except Exception as e:
        print(f"ERROR: Error rendering template '{template_name}': {e}")
        return HttpResponse(f"Internal server error rendering PDF: {e}", status=500)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{pdf_name}.pdf"'

    try:
        print("DEBUG: Attempting to generate PDF with WeasyPrint.")
        HTML(string=html_string).write_pdf(response)
        print("DEBUG: PDF generated successfully.")
    except Exception as e:
        print(f"ERROR: Error generating PDF with WeasyPrint: {e}")
        return HttpResponse(f"Internal server error generating PDF: {e}", status=500)
        
    return response


from django.contrib.auth.models import User
from django.contrib.auth.decorators import user_passes_test

def supervisor_required(view_func):
    decorated_view_func = login_required(user_passes_test(is_supervisor)(view_func))
    return decorated_view_func

@supervisor_required
def reporte_usuarios(request):
    usuarios = User.objects.all().order_by('username')
    return render(request, 'reporte_usuarios.html', {'usuarios': usuarios})

@supervisor_required
def perfil_usuario(request, usuario_id):
    from datetime import date
    usuario = get_object_or_404(User, id=usuario_id)
    oportunidades = TodoItem.objects.filter(usuario=usuario).select_related('cliente')

    today = date.today()
    mes_actual = str(today.month).zfill(2)
    # Oportunidades del mes actual
    oportunidades_mes = oportunidades.filter(mes_cierre=mes_actual)

    # Oportunidad más grande (1-99% probabilidad, cualquier mes)
    oportunidad_mayor = oportunidades.filter(probabilidad_cierre__gte=1, probabilidad_cierre__lte=99).order_by('-monto').first()

    # Total cobrado del mes actual (probabilidad 100%)
    oportunidades_cobradas_mes = oportunidades_mes.filter(probabilidad_cierre=100)
    monto_total_cobrado_mes = oportunidades_cobradas_mes.aggregate(suma=Sum('monto'))['suma'] or 0

    # Oportunidades por cobrar del mes actual (probabilidad > 70% y < 100%)
    oportunidades_por_cobrar_mes = oportunidades_mes.filter(probabilidad_cierre__gt=70, probabilidad_cierre__lt=100)
    monto_total_por_cobrar_mes = oportunidades_por_cobrar_mes.aggregate(suma=Sum('monto'))['suma'] or 0

    # Oportunidades creadas en el mes actual (año y mes actual)
    oportunidades_creadas_mes = oportunidades.filter(fecha_creacion__year=today.year, fecha_creacion__month=today.month)
    oportunidades_creadas_mes_count = oportunidades_creadas_mes.count()

    context = {
        'usuario': usuario,
        'oportunidades': oportunidades.order_by('-monto'),
        'oportunidad_mayor': oportunidad_mayor,
        'oportunidades_cobradas_mes': oportunidades_cobradas_mes,
        'monto_total_cobrado_mes': monto_total_cobrado_mes,
        'oportunidades_por_cobrar_mes': oportunidades_por_cobrar_mes,
        'monto_total_por_cobrar_mes': monto_total_por_cobrar_mes,
        'mes_actual': today.strftime('%B').capitalize(),
        'oportunidades_creadas_mes_count': oportunidades_creadas_mes_count,
    }
    return render(request, 'perfil_usuario.html', context)


from django.template.context_processors import request as request_context

def add_is_supervisor_to_context(request):
    return {'is_supervisor': is_supervisor(request.user) if request.user.is_authenticated else False}

@login_required
def cotizaciones_view(request):
    user = request.user
    is_supervisor = user.groups.filter(name='Supervisores').exists()
    if is_supervisor:
        clientes = Cliente.objects.all().order_by('nombre_empresa')
    else:
        clientes = Cliente.objects.filter(asignado_a=user).order_by('nombre_empresa')

    clientes_data = []
    for cliente in clientes:
        if is_supervisor:
            cotizaciones = Cotizacion.objects.filter(cliente=cliente)
        else:
            cotizaciones = Cotizacion.objects.filter(cliente=cliente, created_by=user)
        cotizaciones_list = [
            {
                'nombre': c.nombre_cotizacion or c.titulo or f'Cotización #{c.id}',
                'descargar_url': f"/cotizacion/pdf/{c.id}/"
            }
            for c in cotizaciones
        ]
        clientes_data.append({
            'id': cliente.id,
            'nombre': cliente.contacto_principal or cliente.nombre_empresa,
            'empresa': cliente.nombre_empresa,
            'cotizaciones': cotizaciones_list
        })
    return render(request, 'cotizaciones.html', {
        'clientes_asignados': clientes_data,
        'is_supervisor': is_supervisor
    })

@login_required
def cotizaciones_por_cliente_view(request, cliente_id):
    user = request.user
    is_supervisor = user.groups.filter(name='Supervisores').exists()
    cliente = get_object_or_404(Cliente, id=cliente_id)
    if is_supervisor:
        cotizaciones = Cotizacion.objects.filter(cliente=cliente)
    else:
        cotizaciones = Cotizacion.objects.filter(cliente=cliente, created_by=user)
    cotizaciones_list = [
        {
            'id': c.id,
            'nombre_cotizacion': c.nombre_cotizacion or c.titulo or f'Cotización #{c.id}',
            'descargar_url': f"/cotizacion/pdf/{c.id}/"
        }
        for c in cotizaciones
    ]
    return render(request, 'cotizaciones_cliente.html', {
        'cliente': cliente,
        'cotizaciones': cotizaciones_list,
        'is_supervisor': is_supervisor
    })
