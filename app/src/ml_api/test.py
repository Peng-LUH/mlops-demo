from ml_api.model import ModelService

model_service = ModelService()


print(model_service.model.eval())
# prediction = model_service.predict(features=[1, 2, 3])

# print(prediction)
