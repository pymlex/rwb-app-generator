FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /source
COPY backend/App.csproj backend/
COPY backend/packages.lock.json backend/
COPY backend-unit/Unit.csproj backend-unit/
RUN dotnet restore backend-unit/Unit.csproj
COPY backend/ backend/
COPY backend-unit/ backend-unit/
RUN dotnet publish backend-unit/Unit.csproj -c Release -o /app --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
COPY --from=build /app .
USER app
ENTRYPOINT ["dotnet", "Unit.dll"]
