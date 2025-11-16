document.addEventListener('DOMContentLoaded', () => {

    let currentQuestions = [];
    let questionIndex = 0;
    let questionnaireResults = [];
    let isNivelamento = true;
    
    const questionnaireAreaEl = document.getElementById('questionnaire-area');
    const loadingAreaEl = document.getElementById('loading-area');

    const questionTextEl = document.getElementById('question-text');
    const choicesContainerEl = document.getElementById('choices-container');
    const feedbackAreaEl = document.getElementById('feedback-area');
    const nextButtonEl = document.getElementById('next-button');
    const questionNumberEl = document.getElementById('question-number');
    const progressBarEl = document.getElementById('progress-bar');
    const questionnaireTitlePrefixEl = document.getElementById('questionnaire-title-prefix');

    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    async function fetchInitialQuestions() {
        try {
            const response = await fetch('/api/questionnaire/start/');
            if (!response.ok) throw new Error('Erro ao buscar questões');
            
            currentQuestions = await response.json();
            startquestionnaire();
        } catch (error) {
            questionTextEl.innerText = 'Não foi possível carregar o questionnaire. Tente novamente.';
            console.error(error);
        }
    }

    function startquestionnaire() {
        questionIndex = 0;
        questionnaireResults = [];
        displayQuestion();
    }


    function displayQuestion() {
        const question = currentQuestions[questionIndex];
        const numQuestions = (questionIndex + 1)

        if (isNivelamento) {
            questionnaireTitlePrefixEl.innerText = "Nivelamento";
        } else {
            questionnaireTitlePrefixEl.innerText = "Recomendando";
        }

        feedbackAreaEl.classList.add('d-none');
        nextButtonEl.classList.add('d-none');
        choicesContainerEl.innerHTML = '';

        questionTextEl.innerText = numQuestions + ") " + question.text;
        questionNumberEl.innerText = questionIndex + 1;
        
        const progress = (numQuestions / 5) * 100;
        progressBarEl.style.width = `${progress}%`;
        progressBarEl.setAttribute('aria-valuenow', progress);
        progressBarEl.innerText = `${progress}%`;


        question.choices.forEach((choice, index) => {
            const button = document.createElement('button');
            const prefix = String.fromCharCode(97 + index) + ") ";

            button.type = 'button';
            button.innerText = prefix + choice.text;
            button.classList.add('list-group-item', 'list-group-item-action', 'choice-btn');
            
            button.dataset.isCorrect = choice.is_correct;
            button.dataset.questionId = question.id;
            button.dataset.subject = question.subject;

            button.addEventListener('click', handleChoiceClick);
            choicesContainerEl.appendChild(button);
        });
    }

    function handleChoiceClick(event) {
        const selectedButton = event.target;
        const isCorrect = selectedButton.dataset.isCorrect === 'true';

        questionnaireResults.push({
            question_id: parseInt(selectedButton.dataset.questionId),
            subject: selectedButton.dataset.subject,
            was_correct: isCorrect
        });

        
        const allChoiceButtons = choicesContainerEl.querySelectorAll('.choice-btn');
        allChoiceButtons.forEach(btn => {
            // btn.disabled = true;
            // btn.classList.remove('list-group-item-action'); 
            btn.classList.add('no-click')
            
            if (btn.dataset.isCorrect === 'true') {
                btn.classList.add('list-group-item-success');
            } else {
                btn.classList.add('text-danger');
            }
        });

        if (isCorrect) {
            feedbackAreaEl.innerText = "Correto! 🎉";
            feedbackAreaEl.classList.remove('d-none', 'alert-danger');
            feedbackAreaEl.classList.add('alert', 'alert-success');
        } else {
            feedbackAreaEl.innerText = "Incorreto!!!";
            feedbackAreaEl.classList.remove('d-none', 'alert-success');
            feedbackAreaEl.classList.add('alert', 'alert-danger');
        }

        nextButtonEl.classList.remove('d-none');
        if (questionIndex === 4) {
            nextButtonEl.innerText = "Finalizar e Carregar Novas Questões";
        } else {
            nextButtonEl.innerText = "Próxima Questão";
        }
    }

    function handleNextClick() {
        questionIndex++;

        if (questionIndex < 5) {
            displayQuestion();
        } else {
            fetchNextQuestions();
        }
    }

    async function fetchNextQuestions() {
        const wrongSubjects = questionnaireResults
            .filter(result => !result.was_correct)
            .map(result => result.subject);
            
        const answeredIds = questionnaireResults.map(result => result.question_id);

        questionTextEl.innerText = "Carregando novas questões com base nos seus erros...";
        isNivelamento = false;
        
        choicesContainerEl.innerHTML = '';
        questionnaireAreaEl.classList.add('d-none');
        feedbackAreaEl.classList.add('d-none');
        nextButtonEl.classList.add('d-none');

        loadingAreaEl.classList.remove('d-none');
        await sleep(2000);

        try {
            const response = await fetch('/api/questionnaire/next/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken') 
                },
                body: JSON.stringify({
                    wrong_subjects: [...new Set(wrongSubjects)],
                    answered_ids: answeredIds
                })
            });

            if (!response.ok) throw new Error('Erro ao buscar próximas questões');
            
            currentQuestions = await response.json();
            loadingAreaEl.classList.add('d-none');

            if (currentQuestions.length === 0) {
                questionnaireAreaEl.classList.remove('d-none');
                questionTextEl.innerText = "Parabéns, você completou todas as questões disponíveis!";
                return;
            }

            questionnaireAreaEl.classList.remove('d-none');
            startquestionnaire();

        } catch (error) {
            loadingAreaEl.classList.add('d-none');
            questionnaireAreaEl.classList.remove('d-none');
            questionTextEl.innerText = 'Não foi possível carregar o próximo questionnaire.';
            console.error(error);
        }
    }

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }


    nextButtonEl.addEventListener('click', handleNextClick);
    fetchInitialQuestions();
});