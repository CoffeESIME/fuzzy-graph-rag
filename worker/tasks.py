from worker.celery_app import celery_app

@celery_app.task
def example_task(word: str):
    return f"processed {word}"
