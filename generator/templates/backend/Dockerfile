FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /source
COPY App.csproj .
COPY packages.lock.json .
RUN dotnet restore --locked-mode
COPY . .
RUN dotnet publish -c Release -o /app --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
COPY --from=build /app .
COPY migrations ./migrations
ENV ASPNETCORE_HTTP_PORTS=8080
USER app
EXPOSE 8080
ENTRYPOINT ["dotnet", "App.dll"]
