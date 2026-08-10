# Contexto FR5-FR6

Documento para registrar lo implementado para cumplir los requisitos del Sprint 1 asignados:

- FR5: unirse a un partido público cuando un jugador registrado lo solicita, sin necesidad de aprobación del organizador.
- FR6: dejar un partido al que el jugador se había unido previamente.

## Estado general al iniciar

Se partió de la base ya construida para FR1 y FR2 (`ContextoFR1-FR2.md`): existían los modelos `users.User` y `matches.Match`, junto con las vistas de listado, detalle, creación y edición de partidos. No existía todavía ningún modelo para representar la participación de un jugador en un partido; `MatchParticipant` solo estaba definido a nivel de diseño lógico en `ContextoGeneral.md`.

## Decisión arquitectónica principal

Se creó el modelo `matches.MatchParticipant`, ya que tanto FR5 como FR6 (y más adelante FR4, FR7, FR8, FR10, FR11) dependen de él. Se decidió:

- Usar una restricción de unicidad `(match, player)` en vez de crear/borrar filas libremente, para respetar la regla de integridad "un jugador no puede aparecer dos veces en el mismo partido".
- No borrar la fila cuando un jugador se sale del partido (FR6). En su lugar se cambia el campo `status` a `left`, para respetar la regla de integridad "la información histórica debe preservarse". Si el jugador vuelve a unirse, la misma fila se reactiva a `status=confirmed`.
- Incluir `attendance_confirmed` desde ahora (aunque su uso real es de FR7, Sprint 2) porque ya estaba en el modelo lógico de la base de datos y evita una migración adicional más adelante.

## Lo que se hizo

### 1. Modelo `MatchParticipant` (`matches/models.py`)

- Campos: `match` (FK a `Match`), `player` (FK a `AUTH_USER_MODEL`), `status` (`confirmed` / `left`), `attendance_confirmed`, `joined_at`, `updated_at`.
- `UniqueConstraint(fields=['match', 'player'])`.
- Se agregaron propiedades de conveniencia en `Match`: `confirmed_participants_count`, `is_full`, `has_started`.
- Migración generada: `matches/migrations/0003_matchparticipant.py`.

### 2. Vistas (`matches/views.py`)

- `MatchJoinView` (FR5): requiere login. Valida, en orden:
	1. Que el usuario no sea el organizador del partido.
	2. Que el partido sea `public` (si es `approval_required`, se redirige con mensaje indicando que requiere aprobación del organizador; ese flujo corresponde a FR4 y no se implementa aquí).
	3. Que el partido no haya comenzado (`date_time` en el pasado).
	4. Que el jugador no esté ya unido (`status=confirmed`).
	5. Que el partido no esté lleno (`confirmed_participants_count >= max_players`).
	- Si todo es válido, crea el `MatchParticipant` o reactiva uno existente con `status=left`.
- `MatchLeaveView` (FR6): requiere login. Busca un `MatchParticipant` del usuario con `status=confirmed` para ese partido; si existe, lo cambia a `status=left`. Si no existe, informa que el usuario no participa en el partido.
- Ambas vistas solo aceptan `POST` y devuelven feedback mediante `django.contrib.messages` (requisito UR3: acciones críticas deben mostrar confirmación).
- Se amplió `MatchDetailView` para exponer `user_is_organizer` y `user_is_participant` en el contexto, usados por la plantilla para decidir qué botón mostrar.

### 3. URLs (`matches/urls.py`)

- `matches/<pk>/join/` → `match_join`
- `matches/<pk>/leave/` → `match_leave`

### 4. Admin (`matches/admin.py`)

- Se registró `MatchParticipant` con `list_display`, `list_filter` y `search_fields`, siguiendo el mismo estilo que `MatchAdmin`.

### 5. Plantillas

- `matches/match_detail.html`: se agregó el conteo "Players joined: X / max_players" y, según el estado del usuario, uno de estos botones/mensajes:
	- Organizador → enlace a editar + texto indicando que es el organizador.
	- Participante confirmado → botón "Leave match".
	- No participante, partido público, no lleno, no iniciado → botón "Join match".
	- No participante, partido `approval_required` / lleno / iniciado → mensaje explicativo (sin botón).
	- Usuario no autenticado → enlace a login.
- `core/base.html`: se agregó el renderizado de `django.contrib.messages` (antes no se mostraba ningún mensaje en la interfaz, aunque el middleware ya estaba activo).
- `config/settings.py`: se agregó `MESSAGE_TAGS` para mapear el nivel `error` de Django al color `danger` de Bootstrap.

### 6. Pruebas (`matches/tests.py`)

Se agregaron `MatchJoinViewTests` y `MatchLeaveViewTests` cubriendo:

- Login requerido en ambas vistas.
- Unión exitosa a partido público.
- Bloqueo al intentar unirse a partido `approval_required`.
- Bloqueo al intentar unirse dos veces.
- Bloqueo al organizador para unirse a su propio partido.
- Bloqueo al unirse a un partido lleno.
- Bloqueo al unirse a un partido que ya empezó.
- Salida exitosa de un partido (cambia `status` a `left`).
- Que salir libera cupo y permite volver a unirse (reutiliza la misma fila).
- Que un usuario que no participaba no pueda "salir" de un partido.

### Validación

- `python manage.py makemigrations matches` generó la migración `0003_matchparticipant` correctamente.
- `python manage.py check` no reportó problemas.
- `python manage.py test users matches` → 19 pruebas, todas exitosas (las 12 existentes de FR1/FR2 + 7 nuevas de FR5/FR6).

## Decisiones técnicas tomadas

- No se implementó el flujo de aprobación (FR4) ni la lista de espera (FR10); ambos quedan fuera de alcance y se referencian explícitamente en el código y en los mensajes de la interfaz para que quien implemente FR4/FR10 sepa dónde conectar su lógica.
- No se muestra el listado de participantes (eso es FR8, Sprint 2); solo se muestra el conteo, necesario para que FR5 pueda validar cupo disponible.
- Se reutiliza la misma fila de `MatchParticipant` entre unirse/salir/volver a unirse en vez de crear una nueva cada vez, para cumplir la restricción de unicidad `(match, player)` sin perder el historial de cuándo se unió originalmente.

## Nota para el equipo

- `MatchParticipant` es un modelo compartido: quien implemente FR4 (solicitudes de unión a partidos con aprobación) y FR7/FR8 (confirmación de asistencia y ver participantes) va a trabajar sobre este mismo modelo. Recomendado coordinar antes de modificarlo para evitar conflictos de migración al hacer merge.
- Este archivo debe actualizarse cada vez que se implemente un paso nuevo, igual que se hizo con `ContextoFR1-FR2.md`.
