$(document).ready(function() {
    $('.create-form').submit(function(e) {
        var deltaValue = parseFloat($('#delta').val());
        var baselineValue = parseFloat($('#baseline').val());

        if (isNaN(deltaValue) || deltaValue < 0 || deltaValue > 1) {
            e.preventDefault();
            $('#delta').addClass('error');
            $('#delta-error').text('Диапазон значений Delta должен быть от 0 до 1');
        } else {
            $('#delta').removeClass('error');
            $('#delta-error').text('');
        }

        if (isNaN(baselineValue) || baselineValue < 0 || baselineValue > 1) {
            e.preventDefault();
            $('#baseline').addClass('error');
            $('#baseline-error').text('Диапазон значений Baseline должен быть от 0 до 1');
        } else {
            $('#baseline').removeClass('error');
            $('#baseline-error').text('');
        }
    });
});
