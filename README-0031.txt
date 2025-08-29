Patch 0031
- Fix: User modal no longer opens automatically.
- Users feature detection: if `/api/users` returns 404, the Users tab is hidden and not loaded.
- Lazy-load Users only when the Users tab is opened.
- Modal is dismissable via Cancel button, clicking the backdrop, or pressing ESC.
Files:
- backend/web/admin.html
