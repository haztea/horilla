class DateFormattingUtility {
    constructor() {
        // Default date format
        this.dateFormat = 'MMM. D, YYYY';
    }

    setDateFormat(format) {
        // Save the selected format to localStorage
        localStorage.setItem('selectedDateFormat', format);
        this.dateFormat = format;
    }

    getFormattedDate(date) {

        if (localStorage.getItem('selectedDateFormat')){

        }
        else{
            function fetchData(callback) {

                $.ajax({
                    url: '/settings/get-date-format/',
                    method: 'GET',
                    data: { csrfmiddlewaretoken: getCookie('csrftoken') },
                    success: function(response) {
                        var date_format = response.selected_format;

                        // Call the callback function and pass the value of 'date_format'
                        callback(date_format);
                    },
                });
            }

            // Use the fetchData function with a callback
            fetchData(function(date_format) {

                // If any date format is found setting it to the local storage.
                if(date_format){
                    localStorage.setItem('selectedDateFormat', date_format);

                }
                // Setting a default date format MMM. D, YYYY
                else{
                    localStorage.setItem('selectedDateFormat', 'MMM. D, YYYY');
                }
            });

        }
        // Use the stored date format
        const storedDateFormat = localStorage.getItem('selectedDateFormat') || 'MMM. D, YYYY';


        // Preprocess the date string based on the selected format
        let processedDate = date;
        if (storedDateFormat === 'DD-MM-YYYY') {
            processedDate = date.replace(/(\d{2})-(\d{2})-(\d{4})/, '$3-$2-$1');
        } else if (storedDateFormat === 'DD.MM.YYYY') {
            processedDate = date.replace(/(\d{2})\.(\d{2})\.(\d{4})/, '$3-$2-$1');
        } else if (storedDateFormat === 'DD/MM/YYYY') {
            processedDate = date.replace(/(\d{2})\/(\d{2})\/(\d{4})/, '$3-$2-$1');
        }

        // Format the processed date using moment.js
        const formattedDate = moment(processedDate).format(storedDateFormat);

        return formattedDate;
    }


}

// Create an instance of the utility
const dateFormatter = new DateFormattingUtility();

// Retrieve the selected date format from localStorage
const storedDateFormat = localStorage.getItem('selectedDateFormat');

if (storedDateFormat) {
    // If a date format is stored, set it in the utility
    dateFormatter.setDateFormat(storedDateFormat);
}
