document.addEventListener('DOMContentLoaded', function () {
    function toggleFields() {
        const protocolSelect = document.querySelector('#id_protocol');

        const modbusFields = document.querySelectorAll(`
            .form-row.field-slave_id,
            .form-row.field-register_type,
            .form-row.field-start_address,
            .form-row.field-bytes_count,
            .form-row.field-port
        `);

        if (!protocolSelect) return;

        const value = protocolSelect.value;
        console.log('Protocol value:', value);

        if (value === 'modbus') {
            modbusFields.forEach(el => el.style.display = '');
        } else if (value === 'dlms') {
            modbusFields.forEach(el => el.style.display = 'none');
        }
        console.log('Found fields:', modbusFields);
    }

    toggleFields();
    document.querySelector('#id_protocol')?.addEventListener('change', toggleFields);
});
