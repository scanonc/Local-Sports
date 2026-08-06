# Contexto FR1-FR2

Documento para registrar lo implementado hasta ahora y lo que sigue para cumplir únicamente los requisitos del Sprint 1:

- FR1: crear un partido de fútbol cuando un jugador registrado envía el formulario de creación.
- FR2: guardar los detalles del partido, incluyendo fecha, hora, ubicación, nivel de habilidad, máximo de jugadores y visibilidad.

## Estado general

La base técnica del proyecto ya fue analizada y el repositorio estaba casi vacío a nivel funcional. No había lógica previa reutilizable en `core`, `users` o `matches`, solo el esqueleto generado por Django.

La decisión arquitectónica principal fue introducir desde el inicio un usuario personalizado en `users`, porque el contexto del proyecto exige campos adicionales y FR1 depende de un organizador autenticado.

## Lo que ya se hizo

### 1. Análisis inicial del proyecto

- Se revisó `Contexto.md` para alinear la implementación con el alcance del MVP.
- Se verificó que el proyecto no tenía modelos, vistas, formularios ni rutas funcionales.
- Se confirmó que Django estaba configurado con SQLite en desarrollo.
- Se identificó que no existía carpeta de templates al inicio.

### 2. Base de configuración

- Se registraron las apps locales `core`, `users` y `matches` en `INSTALLED_APPS`.
- Se configuró `AUTH_USER_MODEL = 'users.User'`.
- Se definieron rutas de login y redirección para el flujo de autenticación del sitio.
- Se conectó `config/urls.py` con la home, las URLs de `users` y las URLs de `matches`.

### 3. Modelo de usuario

- Se creó `users.User` heredando de `AbstractUser`.
- Se agregó `email` único.
- Se agregaron `skill_level`, `profile_picture` y `created_at`.
- Se registró el usuario personalizado en el admin.

### 4. Modelo de partido

- Se creó `matches.Match`.
- Se agregó la relación `organizer` hacia el usuario autenticado.
- Se definieron los campos de negocio requeridos por FR2:
	- `title`
	- `date_time`
	- `location`
	- `skill_level`
	- `max_players`
	- `visibility`
- Se añadieron `created_at` y `updated_at` para control interno.
- Se agregaron validaciones de dominio en `clean()` y se forzó `full_clean()` en `save()`.

### 5. Admin

- Se registró `Match` en el admin con list_display, filtros y búsqueda.
- Se amplió la administración del usuario para exponer datos útiles.

### 6. Formulario y vistas de partidos

- Se creó `MatchForm` como `ModelForm`.
- Se configuró `date_time` como `datetime-local` para simplificar la entrada desde la interfaz.
- Se implementaron:
	- vista de detalle del partido
	- vista de creación del partido
	- vista de edición del partido
- Se restringió la edición para que solo el organizador pueda modificar su propio partido.

### 7. Plantillas

- Se creó una base visual mínima con Bootstrap.
- Se creó la home inicial.
- Se crearon plantillas para crear, editar y ver partidos.

### 8. Autenticación de sitio

- Se habilitaron login, logout y signup para usuarios del sitio.
- Se añadió navegación básica para registrarse, iniciar sesión y cerrar sesión.
- Se creó el formulario de registro con los campos necesarios del usuario personalizado.

### 9. Pruebas

- Se crearon pruebas para el modelo de usuario.
- Se crearon pruebas para el modelo de partido.
- Se crearon pruebas para el formulario de partido.
- Se crearon pruebas de vista para verificar:
	- que crear partido requiere autenticación
	- que el usuario autenticado queda como organizador
	- que solo el organizador puede editar
- La suite focalizada `python manage.py test users matches` pasó correctamente.

## Estado actual de implementación

FR1 y FR2 ya tienen una base funcional, validada y consistente con el contexto del proyecto.

Lo que existe hoy permite:

- registrar usuarios en el sitio,
- iniciar sesión,
- crear un partido,
- almacenar los detalles del partido,
- visualizar el detalle,
- y editar el partido solo si pertenece al organizador.

## Lo que sigue por implementar

El siguiente paso recomendado es una mejora de navegación del MVP, sin entrar en Sprint 2:

1. Crear una vista de listado de partidos.
2. Añadir enlaces desde la home para navegar a ese listado.
3. Refinar mensajes de error y presentación de formularios si hace falta.
4. Revisar si conviene añadir tests de vistas para el detalle y la edición exitosa.

## Corrección aplicada al problema de visibilidad

Se revisó el comportamiento reportado por el usuario: los partidos sí se estaban guardando en SQLite, pero no había una vista de listado accesible desde el sitio para verlos después de cerrar sesión y volver a entrar.

### Diagnóstico

- La base de datos `db.sqlite3` contiene la tabla `matches_match`.
- Se confirmaron registros existentes en `Match` y `User`.
- El problema no era de persistencia, sino de exposición de datos en la interfaz.

### Cambio realizado

- Se agregó `MatchListView` en `matches/views.py`.
- Se añadió la ruta `matches/` como listado principal de partidos.
- Se creó la plantilla `matches/match_list.html`.
- Se agregaron enlaces a “Matches” en la navegación y a “Browse matches” en la home.
- Se añadió una prueba que confirma que el listado muestra partidos guardados.

### Validación

- Se volvió a ejecutar `python manage.py test users matches`.
- La suite pasó correctamente.

## Decisiones técnicas tomadas

- Se eligió un usuario personalizado desde el inicio para evitar una migración costosa más adelante.
- Se mantuvo el dominio de partidos en `matches`, no en `core`.
- Se usaron `choices` para `skill_level` y `visibility` para restringir valores válidos.
- Se validó la lógica de negocio en el modelo y no solo en la vista.
- Se evitó introducir elementos de Sprint 2 como participantes, solicitudes, historial o notificaciones.

## Registro de validación

- `python manage.py makemigrations` generó migraciones correctamente.
- `python manage.py test users matches` pasó correctamente.

## Nota de trabajo

Este archivo debe actualizarse cada vez que se implemente un paso nuevo, incluyendo:

- qué se cambió,
- por qué se cambió,
- qué archivo quedó involucrado,
- y qué validación se ejecutó.
