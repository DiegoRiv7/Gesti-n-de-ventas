# Generated by Django 5.2.3 on 2025-06-28 20:24

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='todoitem',
            options={'verbose_name': 'Venta (TodoItem)', 'verbose_name_plural': 'Ventas (TodoItems)'},
        ),
        migrations.RemoveField(
            model_name='todoitem',
            name='completed',
        ),
        migrations.RemoveField(
            model_name='todoitem',
            name='title',
        ),
        migrations.AddField(
            model_name='todoitem',
            name='area',
            field=models.CharField(choices=[('sistemas', 'Sistemas'), ('rh', 'Recursos Humanos'), ('finanzas', 'Finanzas'), ('marketing', 'Marketing'), ('produccion', 'Producción'), ('logistica', 'Logística'), ('otro', 'Otro')], default='otro', help_text='Área a la que se le vendió.', max_length=50),
        ),
        migrations.AddField(
            model_name='todoitem',
            name='contacto',
            field=models.CharField(default='Contacto Desconocido', help_text='Nombre del contacto del cliente.', max_length=255),
        ),
        migrations.AddField(
            model_name='todoitem',
            name='fecha_creacion',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='todoitem',
            name='mes_cierre',
            field=models.CharField(choices=[('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'), ('4', 'Abril'), ('5', 'Mayo'), ('6', 'Junio'), ('7', 'Julio'), ('8', 'Agosto'), ('9', 'Septiembre'), ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre')], default='1', help_text='Mes en el que se espera cerrar la venta.', max_length=2),
        ),
        migrations.AddField(
            model_name='todoitem',
            name='oportunidad',
            field=models.CharField(default='Sin Oportunidad', help_text='Nombre que el vendedor asigna a la venta.', max_length=255),
        ),
        migrations.AddField(
            model_name='todoitem',
            name='probabilidad_cierre',
            field=models.IntegerField(choices=[(0, '0%'), (1, '1%'), (2, '2%'), (3, '3%'), (4, '4%'), (5, '5%'), (6, '6%'), (7, '7%'), (8, '8%'), (9, '9%'), (10, '10%'), (11, '11%'), (12, '12%'), (13, '13%'), (14, '14%'), (15, '15%'), (16, '16%'), (17, '17%'), (18, '18%'), (19, '19%'), (20, '20%'), (21, '21%'), (22, '22%'), (23, '23%'), (24, '24%'), (25, '25%'), (26, '26%'), (27, '27%'), (28, '28%'), (29, '29%'), (30, '30%'), (31, '31%'), (32, '32%'), (33, '33%'), (34, '34%'), (35, '35%'), (36, '36%'), (37, '37%'), (38, '38%'), (39, '39%'), (40, '40%'), (41, '41%'), (42, '42%'), (43, '43%'), (44, '44%'), (45, '45%'), (46, '46%'), (47, '47%'), (48, '48%'), (49, '49%'), (50, '50%'), (51, '51%'), (52, '52%'), (53, '53%'), (54, '54%'), (55, '55%'), (56, '56%'), (57, '57%'), (58, '58%'), (59, '59%'), (60, '60%'), (61, '61%'), (62, '62%'), (63, '63%'), (64, '64%'), (65, '65%'), (66, '66%'), (67, '67%'), (68, '68%'), (69, '69%'), (70, '70%'), (71, '71%'), (72, '72%'), (73, '73%'), (74, '74%'), (75, '75%'), (76, '76%'), (77, '77%'), (78, '78%'), (79, '79%'), (80, '80%'), (81, '81%'), (82, '82%'), (83, '83%'), (84, '84%'), (85, '85%'), (86, '86%'), (87, '87%'), (88, '88%'), (89, '89%'), (90, '90%'), (91, '91%'), (92, '92%'), (93, '93%'), (94, '94%'), (95, '95%'), (96, '96%'), (97, '97%'), (98, '98%'), (99, '99%'), (100, '100%')], default=0, help_text='Probabilidad de cerrar la venta (0-100%).'),
        ),
        migrations.AddField(
            model_name='todoitem',
            name='producto',
            field=models.CharField(choices=[('zebra', 'ZEBRA'), ('panduit', 'PANDUIT'), ('apc', 'APC'), ('avigilon', 'AVIGILON'), ('genetec', 'GENETEC'), ('axis', 'AXIS'), ('desarrollo_app', 'Desarrollo de APP'), ('runrate', 'RUNRATE'), ('poliza', 'Póliza'), ('cisco', 'CISCO')], default='zebra', help_text='Producto o servicio vendido.', max_length=50),
        ),
    ]
