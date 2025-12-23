# # This file holds the HTML template for the shareable survey form.

# HTML_TEMPLATE = """
# <!DOCTYPE html>
# <html lang="en">
# <head>
#     <meta charset="UTF-8">
#     <meta name="viewport" content="width=device-width, initial-scale=1.0">
#     <title>Survey: {survey_title}</title>
#     <link rel="preconnect" href="https://fonts.googleapis.com">
#     <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
#     <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
#     <style>
#         :root {{
#             --primary-color: #3B82F6;
#             --background-color: #F9FAFB;
#             --form-background: #FFFFFF;
#             --text-color: #1F2937;
#             --label-color: #374151;
#             --border-color: #D1D5DB;
#             --success-bg: #D1FAE5;
#             --success-text: #065F46;
#             --error-bg: #FEE2E2;
#             --error-text: #991B1B;
#         }}
#         body {{ 
#             font-family: 'Inter', sans-serif; 
#             margin: 0; 
#             background-color: var(--background-color); 
#             color: var(--text-color);
#             display: flex;
#             justify-content: center;
#             align-items: center;
#             min-height: 100vh;
#             padding: 1em;
#         }}
#         .container {{ 
#             width: 100%;
#             max-width: 700px; 
#             background: var(--form-background); 
#             padding: 2em 2.5em; 
#             border-radius: 12px; 
#             box-shadow: 0 10px 25px rgba(0,0,0,0.1);
#             border: 1px solid var(--border-color);
#         }}
#         h1 {{
#             color: var(--text-color);
#             font-weight: 700;
#             margin-bottom: 0.25em;
#         }}
#         p {{
#             color: var(--label-color);
#             margin-bottom: 2em;
#         }}
#         .question-block {{ 
#             margin-bottom: 2em; 
#             border-bottom: 1px solid #E5E7EB;
#             padding-bottom: 1.5em;
#         }}
#         .question-block:last-of-type {{
#             border-bottom: none;
#         }}
#         label.main-label {{ 
#             font-weight: 500; 
#             font-size: 1.1em;
#             display: block; 
#             margin-bottom: 0.5em; 
#             color: var(--label-color);
#         }}
#         textarea, input[type="range"] {{ 
#             width: 100%; 
#             padding: 10px; 
#             border-radius: 6px; 
#             border: 1px solid var(--border-color);
#             transition: border-color 0.2s, box-shadow 0.2s;
#             font-size: 1em;
#             box-sizing: border-box;
#         }}
#         textarea:focus, input[type="range"]:focus {{
#             outline: none;
#             border-color: var(--primary-color);
#             box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
#         }}
#         .radio-group label {{
#             display: inline-flex;
#             align-items: center;
#             margin-right: 1.5em;
#             font-weight: normal;
#         }}
#         input[type="radio"] {{
#             margin-right: 0.5em;
#         }}
#         input[type="submit"] {{ 
#             background-color: var(--primary-color); 
#             color: white; 
#             width: 100%;
#             padding: 12px 15px; 
#             border: none; 
#             border-radius: 6px; 
#             cursor: pointer; 
#             font-size: 1.1em;
#             font-weight: 500;
#             transition: background-color 0.2s;
#         }}
#         input[type="submit"]:hover {{
#             background-color: #2563EB;
#         }}
#         #message {{ 
#             margin-top: 1.5em; 
#             padding: 1em; 
#             border-radius: 6px; 
#             display: none; 
#             text-align: center;
#         }}
#         .success {{ background-color: var(--success-bg); color: var(--success-text); }}
#         .error {{ background-color: var(--error-bg); color: var(--error-text); }}
#     </style>
# </head>
# <body>
#     <div class="container">
#         <h1>{survey_title}</h1>
#         <p>{survey_description}</p>
#         <form id="surveyForm">
#             <!-- Hidden fields for metadata -->
#             <input type="hidden" name="start_time" id="start_time">
#             <input type="hidden" name="end_time" id="end_time">
#             <input type="hidden" name="device_info" id="device_info">
#             <input type="hidden" name="geo_latitude" id="geo_latitude">
#             <input type="hidden" name="geo_longitude" id="geo_longitude">
#             <!-- Questions will be dynamically inserted here -->
#         </form>
#         <div id="message"></div>
#     </div>

#     <script>
#         const surveyQuestions = {survey_questions_json};
#         const form = document.getElementById('surveyForm');
#         const messageDiv = document.getElementById('message');
#         const API_URL = 'http://127.0.0.1:8000/submit/{survey_id}';

#         window.onload = function() {{
#             document.getElementById('start_time').value = new Date().toISOString();
#             document.getElementById('device_info').value = navigator.userAgent;

#             if (navigator.geolocation) {{
#                 navigator.geolocation.getCurrentPosition(function(position) {{
#                     document.getElementById('geo_latitude').value = position.coords.latitude;
#                     document.getElementById('geo_longitude').value = position.coords.longitude;
#                 }}, function(error) {{
#                     console.warn(`Geolocation error: ${{error.message}}`);
#                     document.getElementById('geo_latitude').value = 'Permission Denied';
#                     document.getElementById('geo_longitude').value = 'Permission Denied';
#                 }});
#             }} else {{
#                 document.getElementById('geo_latitude').value = 'Not Supported';
#                 document.getElementById('geo_longitude').value = 'Not Supported';
#             }}
#         }};

#         surveyQuestions.forEach(q => {{
#             const block = document.createElement('div');
#             block.className = 'question-block';
#             const questionId = q.question.replace(/\\s+/g, '_').toLowerCase();

#             const label = document.createElement('label');
#             label.className = 'main-label';
#             label.htmlFor = questionId;
#             label.textContent = q.question;
#             block.appendChild(label);

#             if (q.description) {{
#                 const desc = document.createElement('p');
#                 desc.textContent = q.description;
#                 desc.style.fontSize = '0.9em';
#                 desc.style.color = '#666';
#                 desc.style.margin = '0 0 0.75em 0';
#                 block.appendChild(desc);
#             }}

#             if (q.type === 'yes/no') {{
#                 const radioGroup = document.createElement('div');
#                 radioGroup.className = 'radio-group';
#                 ['Yes', 'No'].forEach(val => {{
#                     const wrapper = document.createElement('span');
#                     const radio = document.createElement('input');
#                     radio.type = 'radio';
#                     radio.name = q.question;
#                     radio.id = questionId + val;
#                     radio.value = val;
#                     const radioLabel = document.createElement('label');
#                     radioLabel.htmlFor = questionId + val;
#                     radioLabel.textContent = val;
#                     wrapper.appendChild(radio);
#                     wrapper.appendChild(radioLabel);
#                     radioGroup.appendChild(wrapper);
#                 }});
#                 block.appendChild(radioGroup);
#             }} else if (q.type === 'rating_1_10') {{
#                 const input = document.createElement('input');
#                 input.type = 'range';
#                 input.name = q.question;
#                 input.id = questionId;
#                 input.min = 1;
#                 input.max = 10;
#                 input.value = 5;
#                 block.appendChild(input);
#             }} else {{
#                 const input = document.createElement('textarea');
#                 input.name = q.question;
#                 input.id = questionId;
#                 input.rows = 3;
#                 block.appendChild(input);
#             }}
#             form.appendChild(block);
#         }});
        
#         const submitButton = document.createElement('input');
#         submitButton.type = 'submit';
#         submitButton.value = 'Submit Survey';
#         form.appendChild(submitButton);

#         form.addEventListener('submit', async (e) => {{
#             e.preventDefault();
#             document.getElementById('end_time').value = new Date().toISOString();
#             const formData = new FormData(form);
#             const data = {{}};
#             for (const [key, value] of formData.entries()) {{
#                 data[key] = value;
#             }}

#             try {{
#                 const response = await fetch(API_URL, {{
#                     method: 'POST',
#                     headers: {{ 'Content-Type': 'application/json' }},
#                     body: JSON.stringify(data)
#                 }});
                
#                 messageDiv.style.display = 'block';
#                 if (response.ok) {{
#                     messageDiv.textContent = 'Thank you! Your response has been recorded.';
#                     messageDiv.className = 'success';
#                     form.reset();
#                 }} else {{
#                     const result = await response.json();
#                     messageDiv.textContent = 'Error: ' + (result.detail || 'Could not submit form.');
#                     messageDiv.className = 'error';
#                 }}
#             }} catch (error) {{
#                 messageDiv.style.display = 'block';
#                 messageDiv.textContent = 'A network error occurred. Please ensure the API server is running and try again.';
#                 messageDiv.className = 'error';
#             }}
#         }});
#     </script>
# </body>
# </html>
# """
# This file holds the HTML template for the shareable survey form.

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Survey: {survey_title}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {{
            font-family: 'Inter', sans-serif;
            background-color: #111827; /* gray-900 */
            background-image:
                linear-gradient(to bottom, rgba(17, 24, 39, 0.8), rgba(17, 24, 39, 0.8)),
                url('https://images.unsplash.com/photo-1605333219693-782d27a1e4a3?q=80&w=1974&auto=format&fit=crop');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}

        .form-container {{
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            animation: fadeIn 1s ease-out;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: scale(0.95); }}
            to {{ opacity: 1; transform: scale(1); }}
        }}

        .focus-ring:focus {{
            outline: none;
            box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.5);
            border-color: #60A5FA;
        }}

        input[type="range"] {{
            -webkit-appearance: none;
            appearance: none;
            width: 100%;
            height: 8px;
            background: rgba(255, 255, 255, 0.3);
            border-radius: 9999px;
            outline: none;
            transition: background .2s;
        }}
        input[type="range"]::-webkit-slider-thumb {{
            -webkit-appearance: none;
            appearance: none;
            width: 24px;
            height: 24px;
            background: white;
            cursor: pointer;
            border-radius: 50%;
            border: 2px solid #3B82F6;
        }}
        input[type="range"]::-moz-range-thumb {{
            width: 24px;
            height: 24px;
            background: white;
            cursor: pointer;
            border-radius: 50%;
            border: 2px solid #3B82F6;
        }}
        .validation-icon {{
            position: absolute;
            right: 12px;
            top: 1rem;
            transform: translateY(0);
            font-size: 1.2rem;
            pointer-events: none;
        }}
        .input-wrapper {{
            position: relative;
        }}
        .example-text {{
            font-size: 0.875rem;
            color: #F87171; /* red-400 */
            margin-top: 0.5rem;
        }}
    </style>
</head>
<body class="flex items-center justify-center min-h-screen p-4 sm:p-6 lg:p-8">
    <div class="form-container w-full max-w-3xl p-6 sm:p-8 md:p-10 rounded-2xl shadow-2xl">
        <div class="text-center mb-10">
            <h1 class="text-3xl sm:text-4xl font-bold text-white shadow-sm">{survey_title}</h1>
            <p class="text-gray-200 mt-3 max-w-2xl mx-auto">{survey_description}</p>
        </div>

        <form id="surveyForm" class="space-y-6">
            <input type="hidden" name="start_time" id="start_time">
            <input type="hidden" name="end_time" id="end_time">
            <input type="hidden" name="device_info" id="device_info">
            <input type="hidden" name="geo_latitude" id="geo_latitude">
            <input type="hidden" name="geo_longitude" id="geo_longitude">
            </form>
        <div id="message" class="mt-6 p-4 rounded-lg text-center font-medium hidden"></div>
    </div>

    <script>
        const surveyQuestions = {survey_questions_json};
        const form = document.getElementById('surveyForm');
        const messageDiv = document.getElementById('message');
        const API_URL = 'http://127.0.0.1:8000/submit/{survey_id}';

        window.onload = function() {{
            document.getElementById('start_time').value = new Date().toISOString();
            document.getElementById('device_info').value = navigator.userAgent;

            if (navigator.geolocation) {{
                navigator.geolocation.getCurrentPosition(function(position) {{
                    document.getElementById('geo_latitude').value = position.coords.latitude;
                    document.getElementById('geo_longitude').value = position.coords.longitude;
                }}, function(error) {{
                    console.warn('Geolocation error: ' + error.message);
                }});
            }}
        }};

        surveyQuestions.forEach(function(q, index) {{
            const block = document.createElement('div');
            block.className = 'question-block p-6 rounded-xl border border-transparent bg-white/10 hover:bg-white/20 transition-colors duration-300';
            const questionId = 'q_' + index + '_' + q.question.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase();

            const label = document.createElement('label');
            label.className = 'block text-md font-semibold text-white';
            label.htmlFor = questionId;
            label.textContent = q.question;
            block.appendChild(label);

            if (q.description) {{
                const desc = document.createElement('p');
                desc.textContent = q.description;
                desc.className = 'text-sm text-gray-300 mt-1 mb-4';
                block.appendChild(desc);
            }}

            let inputElement;
            if (q.type === 'yes/no') {{
                inputElement = document.createElement('div');
                inputElement.className = 'flex items-center gap-x-6 mt-2';
                ['Yes', 'No'].forEach(function(val) {{
                    const wrapper = document.createElement('label');
                    wrapper.className = 'flex items-center cursor-pointer';
                    const radio = document.createElement('input');
                    radio.type = 'radio';
                    radio.name = q.question;
                    radio.id = questionId + '_' + val;
                    radio.value = val;
                    radio.className = 'h-4 w-4 border-gray-300 text-blue-500 focus:ring-blue-400';
                    const radioLabel = document.createElement('span');
                    radioLabel.textContent = val;
                    radioLabel.className = 'ml-2 block text-sm font-medium text-gray-100';
                    wrapper.appendChild(radio);
                    wrapper.appendChild(radioLabel);
                    inputElement.appendChild(wrapper);
                }});
                block.appendChild(inputElement);
            }} else if (q.type === 'rating_1_10') {{
                inputElement = document.createElement('div');
                inputElement.className = 'mt-2';
                const range = document.createElement('input');
                range.type = 'range';
                range.name = q.question;
                range.id = questionId;
                range.min = 1;
                range.max = 10;
                range.value = 5;
                const output = document.createElement('output');
                output.className = 'block text-center mt-2 text-lg font-bold text-white';
                output.textContent = range.value;
                range.oninput = function() {{ output.textContent = range.value; }};
                inputElement.appendChild(range);
                inputElement.appendChild(output);
                block.appendChild(inputElement);
            }} else {{ // 'text' or default
                const wrapper = document.createElement('div');
                wrapper.className = 'input-wrapper mt-2';

                inputElement = document.createElement('textarea');
                inputElement.name = q.question;
                inputElement.id = questionId;
                inputElement.rows = 3;
                inputElement.className = 'block w-full rounded-md border-gray-300/20 bg-white/20 text-white placeholder-gray-300 shadow-sm focus-ring sm:text-sm p-3 pr-10 transition-colors';
                inputElement.placeholder = 'Your answer here...';

                const feedbackIcon = document.createElement('span');
                feedbackIcon.id = 'feedback_' + questionId;
                feedbackIcon.className = 'validation-icon';

                const examplePara = document.createElement('p');
                examplePara.id = 'example_' + questionId;
                examplePara.className = 'example-text hidden';

                wrapper.appendChild(inputElement);
                wrapper.appendChild(feedbackIcon);
                block.appendChild(wrapper);
                block.appendChild(examplePara);

                inputElement.addEventListener('blur', async function(event) {{
                    const answer = event.target.value;
                    examplePara.classList.add('hidden');
                    if (!answer || answer.trim() === '') {{
                        feedbackIcon.textContent = '';
                        event.target.classList.remove('border-green-400', 'border-red-400', 'border-2');
                        event.target.dataset.isValid = 'true';
                        return;
                    }}

                    // Validation disabled - previously used Ollama, now removed for security
                    // All answers are accepted without LLM validation
                    feedbackIcon.textContent = '✅';
                    event.target.classList.remove('border-red-400');
                    event.target.classList.add('border-green-400', 'border-2');
                    event.target.dataset.isValid = 'true';
                    
                    /* Previous validation code - disabled
                    feedbackIcon.textContent = '⏳';
                    try {{
                        const validationResult = await verifyWithOllama(q.question, answer);
                        if (validationResult.valid) {{
                            feedbackIcon.textContent = '✅';
                            event.target.classList.remove('border-red-400');
                            event.target.classList.add('border-green-400', 'border-2');
                            event.target.dataset.isValid = 'true';
                        }} else {{
                            feedbackIcon.textContent = '❌';
                            event.target.classList.remove('border-green-400');
                            event.target.classList.add('border-red-400', 'border-2');
                            event.target.dataset.isValid = 'false';
                            if (validationResult.example) {{
                                examplePara.textContent = 'Example: "' + validationResult.example + '"';
                                examplePara.classList.remove('hidden');
                            }}
                        }}
                    }} catch (error) {{
                        feedbackIcon.textContent = '⚠';
                        console.error(error);
                        event.target.dataset.isValid = 'true';
                    }}
                    */
                }});
            }}
            form.appendChild(block);
        }});

        const submitButton = document.createElement('button');
        submitButton.type = 'submit';
        submitButton.textContent = 'Submit Survey';
        submitButton.className = 'w-full bg-blue-600 text-white font-bold py-3 px-4 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-800 focus:ring-blue-500 transition-all duration-300 text-lg shadow-lg hover:shadow-xl';
        form.appendChild(submitButton);

        // NOTE: Direct browser-to-Gemini API calls require exposing API keys in client code.
        // For security, validation should be done server-side or removed.
        // The following validation function is commented out for security.
        // If needed, implement server-side validation endpoint.
        /*
        async function verifyWithGemini(question, answer) {{
            // This would require a backend proxy to call Gemini API securely
            return {{ valid: true }}; // Simplified - accept all answers
        }}
        */

        form.addEventListener('submit', async function(e) {{
            e.preventDefault();

            // Validation removed for security - was using Ollama, now would need backend proxy
            const invalidFields = form.querySelectorAll('textarea[data-is-valid="false"]');
            if (invalidFields.length > 0) {{
                messageDiv.textContent = 'Please fix the highlighted invalid answers before submitting.';
                messageDiv.className = 'bg-yellow-200/20 text-yellow-200 p-4 rounded-lg text-center font-medium';
                messageDiv.style.display = 'block';
                invalidFields[0].focus();
                return;
            }}

            submitButton.disabled = true;
            submitButton.classList.add('opacity-75');
            submitButton.textContent = 'Submitting...';
            messageDiv.style.display = 'none';

            document.getElementById('end_time').value = new Date().toISOString();
            const formData = new FormData(form);
            const data = {{}};
            for (const [key, value] of formData.entries()) {{
                data[key] = value;
            }}

            try {{
                const response = await fetch(API_URL, {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(data)
                }});

                messageDiv.style.display = 'block';
                if (response.ok) {{
                    messageDiv.textContent = 'Thank you! Your response has been recorded.';
                    messageDiv.className = 'bg-green-200/20 text-green-200 p-4 rounded-lg text-center font-medium';
                    form.reset();
                    form.querySelectorAll('output').forEach(function(o) {{ o.textContent = '5'; }});
                    form.querySelectorAll('textarea').forEach(function(t) {{
                        t.classList.remove('border-green-400', 'border-red-400', 'border-2');
                        t.dataset.isValid = 'true';
                        const feedbackIcon = document.getElementById('feedback_' + t.id);
                        if(feedbackIcon) feedbackIcon.textContent = '';
                        const examplePara = document.getElementById('example_' + t.id);
                        if(examplePara) examplePara.classList.add('hidden');
                    }});
                }} else {{
                    const result = await response.json();
                    messageDiv.textContent = 'Error: ' + (result.detail || 'Could not submit the form.');
                    messageDiv.className = 'bg-red-200/20 text-red-200 p-4 rounded-lg text-center font-medium';
                }}
            }} catch (error) {{
                messageDiv.style.display = 'block';
                messageDiv.textContent = 'A network error occurred while submitting. Please try again.';
                messageDiv.className = 'bg-red-200/20 text-red-200 p-4 rounded-lg text-center font-medium';
            }} finally {{
                submitButton.disabled = false;
                submitButton.textContent = 'Submit Survey';
                submitButton.classList.remove('opacity-75');
            }}
        }});
    </script>
</body>
</html>
"""