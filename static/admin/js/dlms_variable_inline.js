document.addEventListener('DOMContentLoaded', function () {
    function toggleDaysField(container) {
        const typeSelect = container.querySelector('[name$="-data_type"]');
        const daysField = container.querySelector('[name$="-days"]');

        if (!typeSelect || !daysField) return;

        const daysRow = daysField.closest('.form-row') || daysField.closest('div');
        if (typeSelect.value === 'profile') {
            daysRow.style.display = '';
        } else {
            daysRow.style.display = 'none';
        }

        typeSelect.addEventListener('change', () => {
            if (typeSelect.value === 'profile') {
                daysRow.style.display = '';
            } else {
                daysRow.style.display = 'none';
            }
        });
    }

    document.querySelectorAll('.dlms-inline').forEach(toggleDaysField);
});
