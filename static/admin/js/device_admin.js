document.addEventListener('DOMContentLoaded', function () {

    toggleFields();

    document.querySelector('#id_protocol')?.addEventListener('change', toggleFields);

    function toggleFields() {
        const protocolSelect = document.querySelector('#id_protocol');

        const modbusFields = document.querySelectorAll(`
            .form-row.field-slave_id,
            .form-row.field-register_type,
            .form-row.field-start_address,
            .form-row.field-bytes_count
        `);

        const dlmsFields = document.querySelectorAll('.form-row.field-days');

        if (!protocolSelect) return;

        const value = protocolSelect.value;
        console.log('Protocol value:', value);

        if (value === 'modbus') {
            modbusFields.forEach(el => el.style.display = '');
            dlmsFields.forEach(el => el.style.display = 'none');
        } else if (value === 'dlms') {
            modbusFields.forEach(el => el.style.display = 'none');
            dlmsFields.forEach(el => el.style.display = '');
        }
        console.log('Found fields:', modbusFields);

        toggleInlineForms(value);       
    }

    function toggleInlineForms(value) {

        console.log('Value:', value);

        const modbusInline = document.querySelector('.modbus-inline');
        const dlmsInline = document.querySelector('.dlms-inline');
    
        if (value === 'modbus') {
            modbusInline?.classList.remove('hidden');
            dlmsInline?.classList.add('hidden');
        } else if (value === 'dlms') {
            modbusInline?.classList.add('hidden');
            dlmsInline?.classList.remove('hidden');
        }
    }

    function updateInlineRequired(fieldset, enabled) {
        const inputs = fieldset.querySelectorAll('input, select, textarea');
    
        inputs.forEach(input => {
            if (enabled) {
                input.required = true;
            } else {
                input.required = false;
    
                // Imposta valore di default solo se è vuoto
                if (!input.value) {
                    if (input.tagName === 'INPUT') {
                        input.value = '-1';  // oppure '0', '', a seconda del campo
                    }
                }
            }
        });
    }
});
