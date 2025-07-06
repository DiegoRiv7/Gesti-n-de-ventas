from django.shortcuts import render, HttpResponse, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import TodoItem, Cliente
from .forms import VentaForm, VentaFilterForm # Asegúrate de que usa VentaForm
from django.db.models import Sum, Count, F, Q
from django.db.models.functions import Upper, Coalesce
from django.db.models import Value
from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal

# Importaciones para generación de PDF
from weasyprint import HTML
from django.template.loader import render_to_string
from django.http import HttpResponse


# Función auxiliar para comprobar si el usuario es supervisor
def is_supervisor(user):
    return user.groups.filter(name='Supervisores').exists()

# Decorador para vistas que solo deben ser accesibles por supervisores o admins (opcional)
# @user_passes_test(is_supervisor)

# Vistas principales y funcionales
@login_required
def home(request):
    # Determinar si el usuario es un supervisor
    if is_supervisor(request.user):
        # Si es supervisor, obtiene todas las oportunidades de todos los usuarios
        user_opportunities = TodoItem.objects.all()
        print("DEBUG: Usuario es supervisor. Obteniendo todas las oportunidades.")
    else:
        # Si no es supervisor, solo obtiene las oportunidades del usuario actual
        user_opportunities = TodoItem.objects.filter(usuario=request.user)
        print(f"DEBUG: Usuario {request.user.username} es vendedor. Obteniendo sus propias oportunidades.")


    def _get_display_for_value(value, choices_list):
        return dict(choices_list).get(value, value)

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

    # --- DEBUGGING ADICIONAL PARA PRODUCTO MENOS VENDIDO ---
    if producto_menos_vendido_context:
        print(f"DEBUG: home view - producto_menos_vendido_context['producto']: {producto_menos_vendido_context['producto']}")
        print(f"DEBUG: home view - producto_menos_vendido_context['get_producto_display']: {producto_menos_vendido_context['get_producto_display']}")
    else:
        print("DEBUG: home view - producto_menos_vendido_context es None (no hay datos para el producto menos vendido).")
    # --- FIN DEBUGGING ADICIONAL ---


    # --- Lógica para el Próximo Mes y Alerta de Meta ---
    # Obtener el próximo mes
    today = date.today()
    next_month_date = today + relativedelta(months=1)
    next_month_value = next_month_date.month # El valor numérico del mes

    # Obtener el nombre del próximo mes para la visualización (DEFINIDO ANTES DE USARLO)
    next_month_display = dict(TodoItem.MES_CHOICES).get(str(next_month_value).zfill(2), f"Mes {next_month_value}") # Esta es la línea clave

    # Obtener las oportunidades del próximo mes (considerando el rol)
    oportunidades_proximo_mes_query = TodoItem.objects.filter(mes_cierre=str(next_month_value).zfill(2))
    if not is_supervisor(request.user):
        oportunidades_proximo_mes_query = oportunidades_proximo_mes_query.filter(usuario=request.user)

    total_oportunidades_proximo_mes = oportunidades_proximo_mes_query.count()
    total_monto_esperado_proximo_mes = oportunidades_proximo_mes_query.aggregate(sum_monto=Sum('monto'))['sum_monto'] or Decimal('0.00')

    # DEBUG: Esta es la línea donde ocurría el error si next_month_display no estaba definido
    print(f"DEBUG: Oportunidades para el próximo mes ({next_month_display}): {total_oportunidades_proximo_mes} - Monto: {total_monto_esperado_proximo_mes}")


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
    return render (request, "home.html", context)


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
    # Los supervisores no deberían tener acceso a ingresar ventas si solo son para supervisar
    # Si quieres que puedan ingresar ventas, puedes eliminar este user_passes_test
    # Opcional: restringir solo a no-supervisores o a roles específicos
    if is_supervisor(request.user):
        return redirect('home') # O a una página de "Acceso Denegado"

    if request.method == 'POST':
        form = VentaForm(request.POST, user=request.user) # Asegúrate de que usa VentaForm
        if form.is_valid():
            venta = form.save(commit=False)
            venta.usuario = request.user
            venta.save()
            return redirect('ingresar_venta_todoitem_exitosa')
    else:
        form = VentaForm(user=request.user) # Asegúrate de que usa VentaForm

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
            return redirect('todos')
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})

def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('todos')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

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
        cliente_seleccionado = get_object_or_404(Cliente, pk=cliente_id, asignado_a=request.user)
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
        print(f"DEBUG:   - ID: {op.id}, Oportunidad: {op.oportunidad}, Producto: {op.producto}, Probabilidad: {op.probabilidad_cierre}")


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
        meses_display.append(dict(TodoItem.MES_CHOICES).get(mes_key, mes_key)) # Fallback a la clave de dos dígitos si no se encuentra el display

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


@login_required
def generate_quote_pdf(request, pk):
    """
    Genera una cotización en PDF para una oportunidad de venta específica.
    """
    # Asegúrate de que solo el usuario propietario o un supervisor pueda generar la cotización
    if is_supervisor(request.user):
        opportunity = get_object_or_404(TodoItem, pk=pk)
    else:
        opportunity = get_object_or_404(TodoItem, pk=pk, usuario=request.user)

    # Contexto para la plantilla PDF
    context = {
        'opportunity': opportunity,
        'request_user': request.user, # Para mostrar el usuario que genera la cotización
        'current_date': date.today(),
        # Puedes añadir más datos de tu empresa aquí si los tienes en el modelo o settings
        'company_name': 'Tu Empresa de Ventas S.A. de C.V.',
        'company_address': 'Calle Ficticia #123, Colonia Ejemplo, Ciudad de México',
        'company_phone': '+52 55 1234 5678',
        'company_email': 'ventas@tuempresa.com',
    }

    # Renderiza la plantilla HTML a una cadena
    html_string = render_to_string('quote_pdf.html', context)

    # Crea el PDF desde la cadena HTML
    # Puedes añadir un base_url si tienes imágenes o CSS externos que WeasyPrint deba cargar
    # Ejemplo: HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf(...)
    pdf_file = HTML(string=html_string).write_pdf()

    # Crea la respuesta HTTP con el PDF
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="cotizacion_{opportunity.oportunidad}.pdf"'
    return response



# Función de vista para editar una oportunidad de venta existente
@login_required # Asegura que solo usuarios logueados puedan acceder
def editar_venta_todoitem(request, pk):
    # Obtiene la instancia de TodoItem (oportunidad) a editar por su primary key (pk)
    # Si no se encuentra, devuelve un error 404.
    oportunidad = get_object_or_404(TodoItem, pk=pk)

    if request.method == 'POST':
        # Si la solicitud es POST, significa que el usuario ha enviado el formulario con los cambios.
        # Instancia el formulario VentaForm con los datos enviados (request.POST)
        # y, crucialmente, con la instancia existente de la oportunidad (instance=oportunidad).
        # También pasamos el usuario actual (request.user) al formulario.
        form = VentaForm(request.POST, instance=oportunidad, user=request.user)
        if form.is_valid():
            # Si los datos del formulario son válidos, guarda los cambios en la base de datos.
            form.save()
            # Redirige al usuario a la página 'todos' (donde se lista la tabla de oportunidades)
            # después de que la edición sea exitosa.
            return redirect('todos')
    else:
        # Si la solicitud es GET, el usuario está pidiendo ver el formulario de edición.
        # Instancia el formulario VentaForm con la instancia existente de la oportunidad.
        # También pasamos el usuario actual (request.user) al formulario.
        # Esto precarga todos los campos del formulario con los valores actuales de la oportunidad,
        # permitiendo al usuario ver y modificar los datos existentes.
        form = VentaForm(instance=oportunidad, user=request.user)

    # Renderiza el template 'ingresar_venta.html'.
    # Este template se usa tanto para crear nuevas ventas como para editarlas,
    # ya que el formulario (VentaForm) es el mismo.
    # Se pasa el formulario (precargado o vacío) y la instancia de la oportunidad (útil para el template).
    return render(request, 'ingresar_venta.html', {'form': form, 'oportunidad': oportunidad})

# ... (Mantén el resto de tus 600+ líneas de código sin cambios) ...
