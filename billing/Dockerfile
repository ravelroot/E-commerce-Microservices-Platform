FROM maven:3.9-eclipse-temurin-26 AS build
WORKDIR /src
COPY pom.xml .
COPY src ./src
RUN --mount=type=cache,target=/root/.m2 \
    mvn -B -ntp -DskipTests package

FROM eclipse-temurin:21-jre
LABEL org.opencontainers.image.title="Argo · faturamento" \
      org.opencontainers.image.version="1.2.0" \
      org.opencontainers.image.licenses="MIT"
RUN useradd --create-home --uid 10001 argo
WORKDIR /app
COPY --from=build /src/target/billing.jar app.jar
USER argo
EXPOSE 8080
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75", "-XX:+ExitOnOutOfMemoryError", "-jar", "app.jar"]
