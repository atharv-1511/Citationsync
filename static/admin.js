document.addEventListener('DOMContentLoaded', function () {
  const createForm = document.getElementById('create-user-form');
  if (createForm) {
    createForm.addEventListener('submit', async function (e) {
      e.preventDefault();
      const email = document.getElementById('email').value.trim();
      const full_name = document.getElementById('full_name').value.trim();
      const password = document.getElementById('password').value;

      if (!email || !full_name || !password) {
        alert('Email, full name and password are required');
        return;
      }

      try {
        const resp = await fetch('/api/admin/users', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({ email, full_name, password })
        });

        const payload = await resp.json();

        if (!resp.ok) {
          alert(payload.error || 'Unable to create user');
          return;
        }

        // Append the new user to the users table if present
        const usersTableBody = document.querySelector('#users-table tbody');
        if (usersTableBody) {
          const tr = document.createElement('tr');
          tr.dataset.userId = payload.user.id;
          tr.innerHTML = `
            <td>${payload.user.email}</td>
            <td>${payload.user.full_name}</td>
            <td>${payload.user.role}</td>
            <td>${(new Date(payload.user.created_at)).toISOString().slice(0,10)}</td>
            <td>
              <button class="user-delete-btn" data-user-id="${payload.user.id}" style="background: #dc3545; padding: 6px 12px; font-size: 0.85em; box-shadow: none;">Delete</button>
            </td>
          `;
          usersTableBody.prepend(tr);
          attachDeleteHandlers();
        }

        // clear form
        createForm.reset();
        alert('User created successfully');
      } catch (err) {
        console.error(err);
        alert('Error creating user');
      }
    });
  }

  function attachDeleteHandlers() {
    const deleteButtons = document.querySelectorAll('.user-delete-btn');
    deleteButtons.forEach(btn => {
      if (btn.dataset.attached) return;
      btn.dataset.attached = '1';
      btn.addEventListener('click', async function (e) {
        const userId = this.dataset.userId;
        if (!confirm('Delete this user?')) return;
        try {
          const resp = await fetch(`/api/admin/users/${userId}`, {
            method: 'DELETE',
            credentials: 'same-origin'
          });
          const payload = await resp.json();
          if (!resp.ok) {
            alert(payload.error || 'Unable to delete user');
            return;
          }

          // remove row
          const row = this.closest('tr');
          if (row) row.remove();
          alert('User deleted');
        } catch (err) {
          console.error(err);
          alert('Error deleting user');
        }
      });
    });
  }

  attachDeleteHandlers();
});
