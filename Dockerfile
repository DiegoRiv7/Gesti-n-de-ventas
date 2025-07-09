# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    pkg-config \
    default-libmysqlclient-dev \
    build-essential \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    libjpeg-dev \
    zlib1g-dev \
    libwebp-dev \
    default-mysql-client \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    Django==5.2.3 \
    django-widget-tweaks==1.5.0 \
    WeasyPrint==61.2 \
    mysqlclient==2.2.4 \
    gunicorn==21.2.0 \
    python-dateutil==2.8.2 \
    Pillow==10.2.0

# Copy project files
COPY . /app/

# Create static files directory
RUN mkdir -p /app/staticfiles

# Make entrypoint script executable
RUN chmod +x /app/entrypoint.sh

# Expose port
EXPOSE 8000

# Set environment variables for production
ENV DJANGO_SETTINGS_MODULE=cartera_clientes.settings
ENV DEBUG=False

# Run entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]