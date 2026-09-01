### PROMPT DE EJECUCIÓN POR FASES: FR9 Y FR12 (SPRINT 2)

**Rol:** Actúa como un Software Architect y Senior Django Developer dentro de este repositorio.
**Contexto:** El proyecto ya cuenta con la base funcional de usuarios, partidos y participantes del Sprint 1. Tu objetivo es implementar los requisitos **FR9** y **FR12** del Sprint 2.

---

### PRINCIPIOS DE INGENIERÍA Y FORMA DE TRABAJAR

- **Arquitectura sobre velocidad:** Prioriza una arquitectura limpia, mantenible y escalable sobre una implementación rápida.
- **Consistencia de estilo:** Guiate estrictamente por la estructura existente de la app `matches`, respetando los patrones de diseño, convenciones de nombres, uso de `choices`, manejo de mensajes de Django y la modularidad establecida.
- **Sin código fuera de alcance:** No implementes requisitos de sprints futuros ni agregues funcionalidades no solicitadas.
- **Regla de Ejecución Estricta:** Debes trabajar en **DOS FASES SECUENCIALES**. NO implementes ambos requisitos al mismo tiempo. Completa la Fase 1 en su totalidad (código, pruebas y documentación) antes de solicitar confirmación o avanzar a la Fase 2.

---

### FASE 1: Cancelación de Partido y Notificación (FR9)

**Objetivo:** Permitir al organizador cancelar un partido activo y notificar a los participantes registrados.

1. **Inspección y Modelo:**
   - Analiza el modelo `Match` existente.
   - Añade gestión de estado al partido mediante un campo `status` que admita las opciones `'active'` y `'cancelled'` (por defecto `'active'`).
   - Genera y ejecuta las migraciones correspondientes.

2. **Lógica de Negocio y Notificación:**
   - Crea un endpoint/vista de cancelación de uso exclusivo para el organizador del partido. Si otro usuario intenta ejecutar la acción, deniega el acceso con la correspondiente validación de permisos.
   - Aplica el patrón **Stub/Logger** para el servicio de notificación: crea un módulo helper desacoplado que obtenga los participantes confirmados (`MatchParticipant`), registre un log informativo con los destinatarios y proporcione retroalimentación visual al usuario en la interfaz a través de `django.contrib.messages`.

3. **Interfaz de Usuario:**
   - En la vista de detalle del partido (`match_detail.html`), añade la acción de cancelar (con confirmación de seguridad JavaScript) visible únicamente para el organizador.
   - Si el partido ya está cancelado, muestra un aviso/banner destacado advirtiendo que fue cancelado y deshabilita acciones de interacción (unirse, salir, etc.).

4. **Validación y Pruebas (Fase 1):**
   - Escribe pruebas unitarias e integradas en `tests.py` para verificar:
     * Que solo el organizador puede cancelar el partido.
     * Que el estado cambia a cancelado.
     * Que el flujo dispara la notificación/mensaje a los participantes.
   - Ejecuta la suite de pruebas (`python manage.py test users matches`) y confirma que todo pase correctamente antes de dar por cerrada esta fase.

---

### FASE 2: Búsqueda y Filtrado de Partidos (FR12)

*(Ejecutar únicamente al terminar, probar y documentar la Fase 1)*

**Objetivo:** Permitir a los usuarios buscar y filtrar partidos disponibles por ubicación, nivel de habilidad y fecha.

1. **Lógica de Búsqueda y Querysets:**
   - Modifica el queryset de `MatchListView` para que **excluya automáticamente partidos cancelados** (`status='active'`).
   - Implementa filtrado dinámico mediante parámetros HTTP GET:
     * **Ubicación:** Búsqueda parcial e insensible a mayúsculas/minúsculas (`icontains`).
     * **Nivel de Habilidad:** Coincidencia exacta usando las opciones definidas en el modelo (`beginner`, `intermediate`, `advanced`).
     * **Fecha:** Búsqueda de partidos programados **a partir de** la fecha seleccionada (`>=` / `gte`).
   - Conserva los parámetros del filtro en el contexto (`get_context_data`) para mantener el estado de los campos de búsqueda en la plantilla.

2. **Interfaz de Usuario:**
   - Integra la barra/formulario de filtros en la plantilla del listado (`match_list.html`), respetando la estética Bootstrap del proyecto, e incluye una opción para limpiar la búsqueda.

3. **Validación y Pruebas (Fase 2):**
   - Escribe pruebas automatizadas para verificar:
     * Que los partidos cancelados queden excluidos del listado.
     * Que los tres filtros funcionen correctamente tanto de forma individual como combinada.
   - Asegúrate de que todas las pruebas (previas y nuevas) sigan pasando sin errores.

---

### ENTREGABLE DE CADA FASE

Al finalizar cada fase, actualiza la documentación interna del proyecto (o actualiza el archivo markdown de seguimiento del sprint) donde registres:
- Qué cambios se realizaron y qué archivos quedaron involucrados.
- Qué decisiones técnicas se tomaron y su justificación.
- El resultado de la suite de pruebas ejecutada (`python manage.py test users matches`).