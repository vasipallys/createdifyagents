# Complete SSE-First Architecture: React + Spring Boot + Dify AI

> **Version:** 1.0  
> **Date:** 2026-07-15  
> **Stack:** React 18+ | Spring Boot 3.x (WebFlux) | Dify AI  
> **Protocol:** Server-Sent Events (SSE) end-to-end

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Dify AI Configuration](#2-dify-ai-configuration)
3. [Spring Boot Backend](#3-spring-boot-backend)
4. [ReactJS Frontend](#4-reactjs-frontend)
5. [Docker & Deployment](#5-docker--deployment)
6. [Security Hardening](#6-security-hardening)
7. [Advanced Patterns](#7-advanced-patterns)
8. [Troubleshooting Guide](#8-troubleshooting-guide)
9. [Complete Project Structure](#9-complete-project-structure)
10. [Appendix: Dify SSE Event Reference](#10-appendix-dify-sse-event-reference)

---

## 1. Architecture Overview

```
┌─────────────────┐      SSE      ┌──────────────────┐      SSE      ┌─────────────┐
│   React Client  │ ◄────────────► │  Spring Boot     │ ◄────────────► │  Dify AI    │
│  (EventSource)  │   (text/event  │  (WebFlux/SseEm-   │   (text/event │  (Workflow/ │
│                 │    -stream)    │   itter Proxy)    │    -stream)   │   Chat API) │
└─────────────────┘                └──────────────────┘               └─────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Spring Boot as transparent SSE proxy** | No buffering, streams Dify events directly to client |
| **No REST polling fallback** | Pure SSE end-to-end for real-time token streaming |
| **WebFlux (reactive) over WebMvc** | Non-blocking, backpressure-aware, handles thousands of concurrent streams |
| **POST-based SSE consumption in React** | `EventSource` only supports GET; `fetch` + `ReadableStream` allows POST with body |
| **Forward Dify event types natively** | Client receives `message`, `error`, `workflow_finished` etc. unchanged |

### Data Flow

```
User types message
       │
       ▼
React: fetch(POST /api/chat/stream) ──► Spring Boot
                                              │
                                              ▼
                                    WebFlux WebClient
                                    POST /chat-messages
                                    response_mode=streaming
                                              │
                                              ▼
                                    Dify AI ──► LLM generates tokens
                                              │
                                              ▼
                                    SSE events stream back:
                                    data: {"event":"message","answer":"Hello"}
                                    data: {"event":"message","answer":" world"}
                                    data: {"event":"workflow_finished",...}
                                              │
                                              ▼
                                    Spring Boot proxies each event
                                    as ServerSentEvent<Object>
                                              │
                                              ▼
React: ReadableStream reader reads chunks
       Parses SSE format
       Updates state per event type
       Renders streaming text
```

---

## 2. Dify AI Configuration

### 2.1 Dify Setup Steps

1. **Create a Chatflow/Workflow App**
   - Go to Dify Studio → Create from Blank → Select **Chatflow** or **Workflow**
   - Design your LLM pipeline (LLM node, tools, knowledge retrieval, etc.)

2. **Enable Streaming Mode**
   - In the app settings, ensure **"Streaming"** is enabled for the chat interface
   - This makes the API return `text/event-stream` instead of JSON

3. **Get API Credentials**
   - Go to **API Access** → **API Keys**
   - Generate a new key: `your-dify-api-key-here`
   - Note your **Base URL**:
     - Dify Cloud: `https://api.dify.ai/v1`
     - Self-hosted: `http://your-dify-instance/v1`

4. **Note the Conversation ID Behavior**
   - First request: omit `conversation_id` → Dify creates a new conversation
   - Subsequent requests: include `conversation_id` from previous response for multi-turn chat

### 2.2 Dify API Endpoint

```
POST /v1/chat-messages
Authorization: Bearer {api-key}
Content-Type: application/json
```

**Request Body:**
```json
{
  "inputs": {},
  "query": "Hello, how are you?",
  "response_mode": "streaming",
  "conversation_id": "",
  "user": "abc-123",
  "files": []
}
```

**Response:** `Content-Type: text/event-stream`

---

## 3. Spring Boot Backend

### 3.1 Maven Dependencies (`pom.xml`)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
                             http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.2.0</version>
        <relativePath/>
    </parent>

    <groupId>com.example</groupId>
    <artifactId>dify-sse-backend</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>

    <properties>
        <java.version>17</java.version>
    </properties>

    <dependencies>
        <!-- WebFlux for reactive SSE proxying -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-webflux</artifactId>
        </dependency>

        <!-- Validation -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>

        <!-- Lombok -->
        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <optional>true</optional>
        </dependency>

        <!-- Testing -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>io.projectreactor</groupId>
            <artifactId>reactor-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
                <configuration>
                    <excludes>
                        <exclude>
                            <groupId>org.projectlombok</groupId>
                            <artifactId>lombok</artifactId>
                        </exclude>
                    </excludes>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
```

### 3.2 Application Configuration (`application.yml`)

```yaml
# application.yml
server:
  port: 8080
  servlet:
    context-path: /api

# Dify AI Configuration
dify:
  base-url: ${DIFY_BASE_URL:https://api.dify.ai/v1}
  api-key: ${DIFY_API_KEY:your-api-key-here}
  timeout-seconds: 120

# CORS Configuration
cors:
  allowed-origins: ${CORS_ORIGINS:http://localhost:3000}

# Logging
logging:
  level:
    com.example.dify: DEBUG
    reactor.netty: INFO
```

### 3.3 DTOs

#### `DifyChatRequest.java`

```java
package com.example.dify.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Builder;
import lombok.Data;

import java.util.List;
import java.util.Map;

@Data
@Builder
public class DifyChatRequest {

    @JsonProperty("inputs")
    @Builder.Default
    private Map<String, Object> inputs = Map.of();

    @JsonProperty("query")
    private String query;

    @JsonProperty("response_mode")
    @Builder.Default
    private String responseMode = "streaming";

    @JsonProperty("conversation_id")
    private String conversationId;

    @JsonProperty("user")
    private String user;

    @JsonProperty("files")
    @Builder.Default
    private List<Object> files = List.of();
}
```

#### `DifyStreamEvent.java`

```java
package com.example.dify.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class DifyStreamEvent {

    @JsonProperty("event")
    private String event;

    @JsonProperty("task_id")
    private String taskId;

    @JsonProperty("id")
    private String id;

    @JsonProperty("message_id")
    private Integer messageId;

    @JsonProperty("conversation_id")
    private String conversationId;

    @JsonProperty("answer")
    private String answer;

    @JsonProperty("created_at")
    private Long createdAt;

    @JsonProperty("error")
    private String error;

    @JsonProperty("data")
    private Map<String, Object> data;

    // Additional fields for specific event types
    @JsonProperty("tool_call_id")
    private String toolCallId;

    @JsonProperty("tool_call")
    private Map<String, Object> toolCall;

    @JsonProperty("tool_response")
    private Map<String, Object> toolResponse;
}
```

#### `ChatRequest.java` (Client-facing)

```java
package com.example.dify.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.util.Map;

@Data
public class ChatRequest {

    @NotBlank(message = "Message cannot be empty")
    private String message;

    private String conversationId;

    private Map<String, Object> inputs;
}
```

### 3.4 WebClient Configuration

```java
package com.example.dify.config;

import io.netty.channel.ChannelOption;
import io.netty.handler.timeout.ReadTimeoutHandler;
import io.netty.handler.timeout.WriteTimeoutHandler;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.netty.http.client.HttpClient;

import java.time.Duration;
import java.util.concurrent.TimeUnit;

@Configuration
public class WebClientConfig {

    @Value("${dify.base-url}")
    private String difyBaseUrl;

    @Value("${dify.api-key}")
    private String difyApiKey;

    @Value("${dify.timeout-seconds:120}")
    private int timeoutSeconds;

    @Bean
    public WebClient difyWebClient() {
        HttpClient httpClient = HttpClient.create()
            .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 10000)
            .responseTimeout(Duration.ofSeconds(timeoutSeconds))
            .doOnConnected(conn -> conn
                .addHandlerLast(new ReadTimeoutHandler(timeoutSeconds, TimeUnit.SECONDS))
                .addHandlerLast(new WriteTimeoutHandler(timeoutSeconds, TimeUnit.SECONDS)));

        return WebClient.builder()
            .baseUrl(difyBaseUrl)
            .defaultHeader("Authorization", "Bearer " + difyApiKey)
            .defaultHeader("Content-Type", "application/json")
            .clientConnector(new ReactorClientHttpConnector(httpClient))
            .build();
    }
}
```

### 3.5 Dify Client Service

```java
package com.example.dify.service;

import com.example.dify.dto.DifyChatRequest;
import com.example.dify.dto.DifyStreamEvent;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.util.Objects;

@Service
@RequiredArgsConstructor
@Slf4j
public class DifyClientService {

    private final WebClient difyWebClient;
    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * Streams chat messages from Dify AI.
     * Returns a Flux of DifyStreamEvent that emits each SSE event as it arrives.
     * No buffering - events flow through as soon as Dify sends them.
     */
    public Flux<DifyStreamEvent> streamChat(DifyChatRequest request) {
        log.debug("Streaming chat to Dify. User: {}, Query: {}", request.getUser(), request.getQuery());

        return difyWebClient.post()
            .uri("/chat-messages")
            .bodyValue(request)
            .retrieve()
            .onStatus(
                status -> status.isError(),
                response -> response.bodyToMono(String.class)
                    .map(errorBody -> new DifyApiException(
                        "Dify API error: " + response.statusCode() + " - " + errorBody,
                        response.statusCode().value()
                    ))
            )
            .bodyToFlux(String.class)
            .filter(line -> line.startsWith("data:"))
            .map(line -> line.substring(5).trim())
            .filter(json -> !json.isEmpty())
            .flatMap(json -> {
                try {
                    DifyStreamEvent event = objectMapper.readValue(json, DifyStreamEvent.class);
                    return Mono.just(event);
                } catch (Exception e) {
                    log.error("Failed to parse Dify event JSON: {}", json, e);
                    return Mono.empty();
                }
            })
            .filter(Objects::nonNull)
            .doOnNext(event -> log.debug("Received Dify event: {}", event.getEvent()))
            .doOnError(error -> log.error("Error in Dify stream", error))
            .doOnComplete(() -> log.debug("Dify stream completed"));
    }

    // Custom exception for Dify API errors
    public static class DifyApiException extends RuntimeException {
        private final int statusCode;

        public DifyApiException(String message, int statusCode) {
            super(message);
            this.statusCode = statusCode;
        }

        public int getStatusCode() {
            return statusCode;
        }
    }
}
```

### 3.6 CORS Configuration

```java
package com.example.dify.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.reactive.CorsWebFilter;
import org.springframework.web.cors.reactive.UrlBasedCorsConfigurationSource;

import java.util.List;

@Configuration
public class CorsConfig {

    @Value("${cors.allowed-origins}")
    private String allowedOrigins;

    @Bean
    public CorsWebFilter corsWebFilter() {
        CorsConfiguration config = new CorsConfiguration();
        config.setAllowCredentials(true);
        config.setAllowedOrigins(List.of(allowedOrigins.split(",")));
        config.setAllowedHeaders(List.of("*"));
        config.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE", "OPTIONS"));
        config.setExposedHeaders(List.of("X-Request-Id", "X-Conversation-Id"));

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", config);

        return new CorsWebFilter(source);
    }
}
```

### 3.7 SSE Chat Controller (WebFlux)

```java
package com.example.dify.controller;

import com.example.dify.dto.ChatRequest;
import com.example.dify.dto.DifyChatRequest;
import com.example.dify.dto.DifyStreamEvent;
import com.example.dify.service.DifyClientService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.time.Duration;

@RestController
@RequestMapping("/chat")
@RequiredArgsConstructor
@Slf4j
public class ChatController {

    private final DifyClientService difyClient;

    /**
     * Main SSE streaming endpoint.
     * Proxies Dify's SSE stream to the React client with zero buffering.
     *
     * Produces: text/event-stream
     * Each event contains the original Dify event type and payload.
     */
    @PostMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<ServerSentEvent<DifyStreamEvent>> streamChat(
            @Valid @RequestBody ChatRequest request,
            @RequestHeader(value = "X-User-Id", defaultValue = "anonymous") String userId,
            @RequestHeader(value = "X-Request-Id", required = false) String requestId) {

        String reqId = requestId != null ? requestId : java.util.UUID.randomUUID().toString();
        log.info("[{}] Streaming chat request. User: {}, Conversation: {}",
            reqId, userId, request.getConversationId());

        DifyChatRequest difyRequest = DifyChatRequest.builder()
            .query(request.getMessage())
            .conversationId(request.getConversationId())
            .user(userId)
            .inputs(request.getInputs() != null ? request.getInputs() : java.util.Map.of())
            .responseMode("streaming")
            .build();

        return difyClient.streamChat(difyRequest)
            .map(event -> ServerSentEvent.<DifyStreamEvent>builder()
                .id(event.getId() != null ? event.getId() : reqId)
                .event(event.getEvent())
                .data(event)
                .build())
            .onErrorResume(error -> {
                log.error("[{}] Stream error: {}", reqId, error.getMessage(), error);
                return Flux.just(ServerSentEvent.<DifyStreamEvent>builder()
                    .event("error")
                    .data(DifyStreamEvent.builder()
                        .event("error")
                        .error(error.getMessage())
                        .build())
                    .build());
            })
            .doOnComplete(() -> log.info("[{}] Stream completed", reqId));
    }

    /**
     * Health check endpoint.
     */
    @GetMapping("/health")
    public Mono<String> health() {
        return Mono.just("OK");
    }
}
```

### 3.8 Global Error Handler

```java
package com.example.dify.config;

import com.example.dify.service.DifyClientService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.bind.support.WebExchangeBindingException;

import java.time.Instant;
import java.util.Map;

@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    @ExceptionHandler(DifyClientService.DifyApiException.class)
    public ResponseEntity<Map<String, Object>> handleDifyApiException(DifyClientService.DifyApiException e) {
        log.error("Dify API error: {}", e.getMessage());
        return ResponseEntity.status(e.getStatusCode())
            .body(Map.of(
                "error", "Dify API Error",
                "message", e.getMessage(),
                "timestamp", Instant.now().toString()
            ));
    }

    @ExceptionHandler(WebExchangeBindingException.class)
    public ResponseEntity<Map<String, Object>> handleValidationException(WebExchangeBindingException e) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
            .body(Map.of(
                "error", "Validation Error",
                "message", e.getError().getMessage(),
                "timestamp", Instant.now().toString()
            ));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String, Object>> handleGenericException(Exception e) {
        log.error("Unexpected error: {}", e.getMessage(), e);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
            .body(Map.of(
                "error", "Internal Server Error",
                "message", e.getMessage(),
                "timestamp", Instant.now().toString()
            ));
    }
}
```

### 3.9 Main Application Class

```java
package com.example.dify;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class DifySseApplication {

    public static void main(String[] args) {
        SpringApplication.run(DifySseApplication.class, args);
    }
}
```

---

## 4. ReactJS Frontend

### 4.1 Project Setup

```bash
npx create-react-app dify-sse-frontend --template typescript
cd dify-sse-frontend
npm install
```

### 4.2 Type Definitions (`src/types/dify.ts`)

```typescript
// src/types/dify.ts

export interface DifyStreamEvent {
  event: string;
  task_id?: string;
  id?: string;
  message_id?: number;
  conversation_id?: string;
  answer?: string;
  created_at?: number;
  error?: string;
  data?: Record<string, any>;
  tool_call_id?: string;
  tool_call?: Record<string, any>;
  tool_response?: Record<string, any>;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  isStreaming?: boolean;
  error?: string;
  timestamp: Date;
}

export interface ChatRequest {
  message: string;
  conversationId?: string;
  inputs?: Record<string, any>;
}
```

### 4.3 Custom SSE Hook (`src/hooks/useDifyStream.ts`)

```typescript
// src/hooks/useDifyStream.ts
import { useState, useCallback, useRef } from 'react';
import { DifyStreamEvent, ChatMessage } from '../types/dify';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8080/api';

export interface UseDifyStreamReturn {
  messages: ChatMessage[];
  isStreaming: boolean;
  error: string | null;
  sendMessage: (message: string, inputs?: Record<string, any>) => void;
  stopStream: () => void;
  conversationId: string | null;
  clearMessages: () => void;
}

export const useDifyStream = (): UseDifyStreamReturn => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const currentAssistantIdRef = useRef<string | null>(null);

  const generateId = () => Math.random().toString(36).substring(2, 15);

  const sendMessage = useCallback(
    async (message: string, inputs?: Record<string, any>) => {
      // Stop any existing stream
      stopStream();
      setError(null);
      setIsStreaming(true);

      const userMessage: ChatMessage = {
        id: generateId(),
        role: 'user',
        content: message,
        timestamp: new Date(),
      };

      const assistantId = generateId();
      currentAssistantIdRef.current = assistantId;

      const assistantMessage: ChatMessage = {
        id: assistantId,
        role: 'assistant',
        content: '',
        isStreaming: true,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const response = await fetch(`${API_BASE}/chat/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-User-Id': 'user-123',
            'X-Request-Id': generateId(),
          },
          body: JSON.stringify({
            message,
            inputs: inputs || {},
            conversationId: conversationId || undefined,
          }),
          signal: controller.signal,
        });

        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(`HTTP ${response.status}: ${errorText}`);
        }

        if (!response.body) {
          throw new Error('No response body received');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.trim()) continue;

            // Parse SSE format
            const eventMatch = line.match(/^event:\s*(.+)$/m);
            const dataMatch = line.match(/^data:\s*(.+)$/ms);

            if (dataMatch) {
              try {
                const eventData: DifyStreamEvent = JSON.parse(dataMatch[1]);
                const eventType = eventMatch?.[1] || eventData.event;
                handleEvent(eventType, eventData, assistantId);
              } catch (e) {
                console.error('Failed to parse SSE data:', line, e);
              }
            }
          }
        }

        // Mark streaming as complete
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantId ? { ...msg, isStreaming: false } : msg
          )
        );
      } catch (err: any) {
        if (err.name === 'AbortError') {
          console.log('Stream aborted by user');
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? { ...msg, isStreaming: false, content: msg.content + '\n[Stopped]' }
                : msg
            )
          );
        } else {
          console.error('Stream error:', err);
          setError(err.message);
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? { ...msg, isStreaming: false, error: err.message }
                : msg
            )
          );
        }
      } finally {
        setIsStreaming(false);
        abortControllerRef.current = null;
      }
    },
    [conversationId]
  );

  const handleEvent = (
    eventType: string,
    data: DifyStreamEvent,
    assistantId: string
  ) => {
    switch (eventType) {
      case 'message': {
        // Token chunk from LLM
        if (data.answer) {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? { ...msg, content: msg.content + data.answer }
                : msg
            )
          );
        }
        if (data.conversation_id) {
          setConversationId(data.conversation_id);
        }
        break;
      }

      case 'agent_message': {
        // Agent reasoning step - can be displayed as thought process
        console.log('Agent reasoning:', data);
        break;
      }

      case 'tool_call': {
        // Tool execution started
        console.log('Tool called:', data.tool_call);
        break;
      }

      case 'tool_response': {
        // Tool execution completed
        console.log('Tool response:', data.tool_response);
        break;
      }

      case 'node_finished': {
        // Workflow node completed
        console.log('Node finished:', data.data);
        break;
      }

      case 'workflow_finished':
      case 'message_end': {
        // Stream complete
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantId ? { ...msg, isStreaming: false } : msg
          )
        );
        setIsStreaming(false);
        break;
      }

      case 'error': {
        setError(data.error || 'Unknown error from Dify');
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantId
              ? { ...msg, isStreaming: false, error: data.error }
              : msg
          )
        );
        setIsStreaming(false);
        break;
      }

      case 'ping': {
        // Keep-alive, ignore
        break;
      }

      default: {
        console.log('Unhandled event type:', eventType, data);
      }
    }
  };

  const stopStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setConversationId(null);
    setError(null);
  }, []);

  return {
    messages,
    isStreaming,
    error,
    sendMessage,
    stopStream,
    conversationId,
    clearMessages,
  };
};
```

### 4.4 Chat Interface Component (`src/components/ChatInterface.tsx`)

```tsx
// src/components/ChatInterface.tsx
import React, { useState, useRef, useEffect } from 'react';
import { useDifyStream } from '../hooks/useDifyStream';
import './ChatInterface.css';

export const ChatInterface: React.FC = () => {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const {
    messages,
    isStreaming,
    error,
    sendMessage,
    stopStream,
    conversationId,
    clearMessages,
  } = useDifyStream();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    sendMessage(input.trim());
    setInput('');
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleTextareaInput = (e: React.FormEvent<HTMLTextAreaElement>) => {
    const target = e.currentTarget;
    target.style.height = 'auto';
    target.style.height = Math.min(target.scrollHeight, 200) + 'px';
  };

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="chat-container">
      <header className="chat-header">
        <h1>Dify AI Chat</h1>
        <div className="header-actions">
          {conversationId && (
            <span className="conversation-id" title={conversationId}>
              Session: {conversationId.slice(0, 8)}...
            </span>
          )}
          <button className="clear-btn" onClick={clearMessages}>
            Clear
          </button>
        </div>
      </header>

      <div className="messages-container">
        {messages.length === 0 && (
          <div className="empty-state">
            <p>Start a conversation with Dify AI</p>
            <p className="hint">Type a message below and press Enter</p>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`message ${msg.role} ${msg.isStreaming ? 'streaming' : ''} ${
              msg.error ? 'error' : ''
            }`}
          >
            <div className="message-avatar">
              {msg.role === 'user' ? '👤' : '🤖'}
            </div>
            <div className="message-content">
              <div className="message-text">
                {msg.content || (msg.isStreaming ? <span className="typing">Thinking...</span> : '')}
                {msg.isStreaming && <span className="cursor">▌</span>}
              </div>
              {msg.error && <div className="message-error">Error: {msg.error}</div>}
              <div className="message-meta">
                {msg.timestamp.toLocaleTimeString()}
              </div>
            </div>
          </div>
        ))}

        {error && !messages.some((m) => m.error) && (
          <div className="global-error">
            <span>⚠️ {error}</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <form className="input-area" onSubmit={handleSubmit}>
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleTextareaInput}
          placeholder="Type your message... (Shift+Enter for new line)"
          rows={1}
          disabled={isStreaming}
        />
        {isStreaming ? (
          <button type="button" className="stop-btn" onClick={stopStream}>
            ⏹ Stop
          </button>
        ) : (
          <button
            type="submit"
            className="send-btn"
            disabled={!input.trim()}
          >
            ➤ Send
          </button>
        )}
      </form>
    </div>
  );
};
```

### 4.5 Styles (`src/components/ChatInterface.css`)

```css
/* src/components/ChatInterface.css */

.chat-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 900px;
  margin: 0 auto;
  background: #f5f5f5;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid #e0e0e0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.chat-header h1 {
  margin: 0;
  font-size: 1.25rem;
  color: #1a1a1a;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.conversation-id {
  font-size: 0.75rem;
  color: #666;
  background: #f0f0f0;
  padding: 4px 8px;
  border-radius: 4px;
}

.clear-btn {
  padding: 6px 12px;
  border: 1px solid #ddd;
  background: #fff;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
}

.clear-btn:hover {
  background: #f5f5f5;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty-state {
  text-align: center;
  color: #999;
  margin-top: 40px;
}

.empty-state .hint {
  font-size: 0.875rem;
  color: #bbb;
}

.message {
  display: flex;
  gap: 12px;
  max-width: 85%;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message.assistant {
  align-self: flex-start;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  border: 1px solid #e0e0e0;
  font-size: 1.25rem;
  flex-shrink: 0;
}

.message-content {
  background: #fff;
  padding: 12px 16px;
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
  max-width: 100%;
  word-wrap: break-word;
}

.message.user .message-content {
  background: #007bff;
  color: #fff;
}

.message-text {
  line-height: 1.5;
  white-space: pre-wrap;
}

.message-text .typing {
  color: #999;
  font-style: italic;
}

.cursor {
  display: inline-block;
  animation: blink 1s step-end infinite;
  color: #007bff;
  margin-left: 2px;
}

@keyframes blink {
  50% { opacity: 0; }
}

.message-meta {
  font-size: 0.7rem;
  color: #999;
  margin-top: 6px;
  text-align: right;
}

.message.user .message-meta {
  color: rgba(255,255,255,0.7);
}

.message.error .message-content {
  border: 1px solid #ff4444;
  background: #fff5f5;
}

.message-error {
  color: #ff4444;
  font-size: 0.875rem;
  margin-top: 8px;
  padding: 8px;
  background: #ffeeee;
  border-radius: 6px;
}

.global-error {
  align-self: center;
  background: #ff4444;
  color: #fff;
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 0.875rem;
}

.input-area {
  display: flex;
  gap: 12px;
  padding: 16px 24px;
  background: #fff;
  border-top: 1px solid #e0e0e0;
  align-items: flex-end;
}

.input-area textarea {
  flex: 1;
  padding: 12px 16px;
  border: 1px solid #ddd;
  border-radius: 12px;
  resize: none;
  font-family: inherit;
  font-size: 0.95rem;
  line-height: 1.5;
  min-height: 24px;
  max-height: 200px;
  outline: none;
  transition: border-color 0.2s;
}

.input-area textarea:focus {
  border-color: #007bff;
}

.input-area textarea:disabled {
  background: #f5f5f5;
  cursor: not-allowed;
}

.send-btn, .stop-btn {
  padding: 12px 20px;
  border: none;
  border-radius: 12px;
  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.send-btn {
  background: #007bff;
  color: #fff;
}

.send-btn:hover:not(:disabled) {
  background: #0056b3;
}

.send-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.stop-btn {
  background: #ff4444;
  color: #fff;
}

.stop-btn:hover {
  background: #cc0000;
}

/* Scrollbar styling */
.messages-container::-webkit-scrollbar {
  width: 8px;
}

.messages-container::-webkit-scrollbar-track {
  background: transparent;
}

.messages-container::-webkit-scrollbar-thumb {
  background: #ccc;
  border-radius: 4px;
}

.messages-container::-webkit-scrollbar-thumb:hover {
  background: #aaa;
}
```

### 4.6 App Entry Point (`src/App.tsx`)

```tsx
// src/App.tsx
import React from 'react';
import { ChatInterface } from './components/ChatInterface';
import './App.css';

function App() {
  return (
    <div className="App">
      <ChatInterface />
    </div>
  );
}

export default App;
```

### 4.7 Global Styles (`src/App.css`)

```css
/* src/App.css */

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  background: #e8e8e8;
}

.App {
  min-height: 100vh;
  display: flex;
  justify-content: center;
}
```

### 4.8 Environment Variables (`.env`)

```
# .env (development)
REACT_APP_API_URL=http://localhost:8080/api

# .env.production
REACT_APP_API_URL=https://your-api-domain.com/api
```

---

## 5. Docker & Deployment

### 5.1 Backend Dockerfile (`backend/Dockerfile`)

```dockerfile
# backend/Dockerfile
FROM eclipse-temurin:17-jdk-alpine AS builder

WORKDIR /app
COPY pom.xml .
COPY src ./src
RUN apk add --no-cache maven &&     mvn clean package -DskipTests

FROM eclipse-temurin:17-jre-alpine

WORKDIR /app
COPY --from=builder /app/target/*.jar app.jar

EXPOSE 8080

ENV DIFY_BASE_URL=https://api.dify.ai/v1
ENV DIFY_API_KEY=your-api-key-here
ENV CORS_ORIGINS=http://localhost:3000

ENTRYPOINT ["java", "-jar", "app.jar"]
```

### 5.2 Frontend Dockerfile (`frontend/Dockerfile`)

```dockerfile
# frontend/Dockerfile
FROM node:18-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

### 5.3 Nginx Config (`frontend/nginx.conf`)

```nginx
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml;

    # Handle React Router
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets
    location /static {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### 5.4 Docker Compose (`docker-compose.yml`)

```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8080:8080"
    environment:
      - DIFY_BASE_URL=${DIFY_BASE_URL}
      - DIFY_API_KEY=${DIFY_API_KEY}
      - CORS_ORIGINS=http://localhost:3000,http://frontend:80
    networks:
      - dify-network
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:80"
    depends_on:
      - backend
    networks:
      - dify-network
    restart: unless-stopped

  # Optional: Nginx reverse proxy for production
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - backend
      - frontend
    networks:
      - dify-network
    restart: unless-stopped
    profiles:
      - production

networks:
  dify-network:
    driver: bridge
```

### 5.5 Production Nginx Config (`nginx/nginx.conf`)

```nginx
upstream backend {
    server backend:8080;
}

upstream frontend {
    server frontend:80;
}

server {
    listen 80;
    server_name your-domain.com;

    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # API with SSE support - CRITICAL CONFIGURATION
    location /api/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;

        # SSE-specific headers
        proxy_set_header Connection '';
        proxy_set_header Cache-Control 'no-cache';

        # Disable buffering - ESSENTIAL for SSE
        proxy_buffering off;
        proxy_cache off;

        # Timeouts matching backend
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;

        # Headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 5.6 Environment File (`.env`)

```bash
# .env - never commit this to version control
DIFY_BASE_URL=https://api.dify.ai/v1
DIFY_API_KEY=your-dify-api-key-here
```

---

## 6. Security Hardening

### 6.1 Security Checklist

| Layer | Threat | Mitigation |
|-------|--------|------------|
| **API Key** | Exposure to client | Store only in Spring Boot env vars; never in frontend |
| **CORS** | Cross-origin attacks | Restrict to known domains; no wildcard `*` |
| **User ID** | Spoofing | Validate `X-User-Id` against auth session/token |
| **Rate Limiting** | DoS / cost abuse | Implement per-user rate limits on `/chat/stream` |
| **Input Validation** | Injection attacks | `@Valid` on DTOs; sanitize before sending to Dify |
| **SSE Timeout** | Resource exhaustion | Set 120s max; clean up on client disconnect |
| **Error Info** | Information leakage | Generic error messages to client; log details server-side |

### 6.2 Spring Security Integration (Optional)

```java
// Add to pom.xml: spring-boot-starter-security

@Configuration
@EnableWebFluxSecurity
public class SecurityConfig {

    @Bean
    public SecurityWebFilterChain securityWebFilterChain(ServerHttpSecurity http) {
        return http
            .csrf(csrf -> csrf.disable()) // Disable for SSE endpoints
            .authorizeExchange(exchanges -> exchanges
                .pathMatchers("/api/chat/health").permitAll()
                .pathMatchers("/api/chat/**").authenticated()
                .anyExchange().permitAll()
            )
            .oauth2ResourceServer(oauth2 -> oauth2.jwt())
            .build();
    }
}
```

### 6.3 Rate Limiting with Bucket4j

```xml
<!-- pom.xml -->
<dependency>
    <groupId>com.github.vladimir-bukhtoyarov</groupId>
    <artifactId>bucket4j-core</artifactId>
    <version>8.1.0</version>
</dependency>
```

```java
@Component
public class RateLimitService {
    private final Map<String, Bucket> buckets = new ConcurrentHashMap<>();

    public boolean isAllowed(String userId) {
        Bucket bucket = buckets.computeIfAbsent(userId, k -> 
            Bucket.builder()
                .addLimit(Bandwidth.classic(10, Refill.intervally(10, Duration.ofMinutes(1))))
                .build()
        );
        return bucket.tryConsume(1);
    }
}
```

---

## 7. Advanced Patterns

### 7.1 Connection Resilience & Retry Logic

```typescript
// Add to useDifyStream.ts
const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 1000;

const sendMessageWithRetry = useCallback(async (
  message: string,
  inputs?: Record<string, any>,
  retryCount = 0
): Promise<void> => {
  try {
    await sendMessage(message, inputs);
  } catch (err: any) {
    if (retryCount < MAX_RETRIES && err.name !== 'AbortError') {
      console.warn(`Retry ${retryCount + 1}/${MAX_RETRIES} after ${RETRY_DELAY_MS}ms`);
      await new Promise(resolve => setTimeout(resolve, RETRY_DELAY_MS * (retryCount + 1)));
      return sendMessageWithRetry(message, inputs, retryCount + 1);
    }
    throw err;
  }
}, [sendMessage]);
```

### 7.2 Multi-User Session Isolation

```java
@Component
public class SseSessionManager {
    private final Map<String, FluxSink<ServerSentEvent<DifyStreamEvent>>> sinks = new ConcurrentHashMap<>();

    public void register(String userId, FluxSink<ServerSentEvent<DifyStreamEvent>> sink) {
        sinks.put(userId, sink);
    }

    public void unregister(String userId) {
        sinks.remove(userId);
    }

    public void sendToUser(String userId, ServerSentEvent<DifyStreamEvent> event) {
        FluxSink<ServerSentEvent<DifyStreamEvent>> sink = sinks.get(userId);
        if (sink != null) {
            sink.next(event);
        }
    }
}
```

### 7.3 Streaming Markdown Rendering

```tsx
// Use react-markdown for streaming content
import ReactMarkdown from 'react-markdown';

// In ChatInterface.tsx, replace message-text div:
<div className="message-text">
  <ReactMarkdown>
    {msg.content}
  </ReactMarkdown>
  {msg.isStreaming && <span className="cursor">▌</span>}
</div>
```

### 7.4 File Upload Support

```typescript
// Extend ChatRequest to support files
export interface ChatRequest {
  message: string;
  conversationId?: string;
  inputs?: Record<string, any>;
  files?: File[];
}

// In useDifyStream.ts:
const sendMessage = useCallback(async (message: string, files?: File[]) => {
  const formData = new FormData();
  formData.append('message', message);
  formData.append('conversationId', conversationId || '');
  files?.forEach(file => formData.append('files', file));

  // Use fetch with formData instead of JSON
  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    body: formData,
    signal: controller.signal,
  });
}, []);
```

### 7.5 Conversation History Persistence

```java
@Entity
public class Conversation {
    @Id
    private String id;
    private String userId;
    private String conversationId; // Dify's conversation ID
    private String title;
    private LocalDateTime createdAt;
    @OneToMany(mappedBy = "conversation", cascade = CascadeType.ALL)
    private List<Message> messages;
}

@Entity
public class Message {
    @Id
    private String id;
    @ManyToOne
    private Conversation conversation;
    private String role; // user / assistant
    private String content;
    private LocalDateTime timestamp;
}
```

---

## 8. Troubleshooting Guide

### 8.1 Common Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| **No streaming, full response arrives at once** | Nginx/proxy buffering | Set `proxy_buffering off; proxy_cache off;` |
| **Connection drops after 30s** | Proxy timeout | Increase `proxy_read_timeout` to 120s+ |
| **CORS errors in browser** | Missing CORS headers | Verify `@CrossOrigin` or `CorsWebFilter` config |
| **Dify returns 401 Unauthorized** | Invalid API key | Check `Authorization: Bearer` header format |
| **React not updating during stream** | State batching | Use functional `setState` updates in loop |
| **Memory leak on reconnect** | AbortController not cleaned | Call `abort()` in cleanup/useEffect return |
| **SSE parse errors** | Malformed JSON in stream | Add try-catch around `JSON.parse` |
| **Stream stops mid-response** | Dify timeout | Check Dify app timeout settings; increase if needed |
| **Multiple duplicate messages** | React StrictMode double-mount | Use `useRef` to track stream state |

### 8.2 Debug Logging

```yaml
# application.yml - enable debug logging
logging:
  level:
    com.example.dify: DEBUG
    reactor.netty: DEBUG
    org.springframework.web.reactive: DEBUG
```

```typescript
// frontend - add console logging in useDifyStream
const handleEvent = (eventType: string, data: DifyStreamEvent) => {
  console.log(`[SSE] Event: ${eventType}`, data);
  // ... rest of handler
};
```

### 8.3 Testing SSE with cURL

```bash
# Test the Spring Boot SSE endpoint
curl -N -X POST http://localhost:8080/api/chat/stream   -H "Content-Type: application/json"   -H "X-User-Id: test-user"   -d '{
    "message": "Hello, how are you?",
    "inputs": {}
  }'

# Test Dify directly
curl -N -X POST https://api.dify.ai/v1/chat-messages   -H "Authorization: Bearer YOUR_API_KEY"   -H "Content-Type: application/json"   -d '{
    "inputs": {},
    "query": "Hello",
    "response_mode": "streaming",
    "conversation_id": "",
    "user": "test-user"
  }'
```

---

## 9. Complete Project Structure

```
dify-sse-app/
├── backend/
│   ├── src/
│   │   └── main/
│   │       ├── java/
│   │       │   └── com/
│   │       │       └── example/
│   │       │           └── dify/
│   │       │               ├── DifySseApplication.java
│   │       │               ├── config/
│   │       │               │   ├── CorsConfig.java
│   │       │               │   ├── WebClientConfig.java
│   │       │               │   └── GlobalExceptionHandler.java
│   │       │               ├── controller/
│   │       │               │   └── ChatController.java
│   │       │               ├── dto/
│   │       │               │   ├── ChatRequest.java
│   │       │               │   ├── DifyChatRequest.java
│   │       │               │   └── DifyStreamEvent.java
│   │       │               └── service/
│   │       │                   └── DifyClientService.java
│   │       └── resources/
│   │           └── application.yml
│   ├── pom.xml
│   └── Dockerfile
├── frontend/
│   ├── public/
│   │   ├── index.html
│   │   └── favicon.ico
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatInterface.tsx
│   │   │   └── ChatInterface.css
│   │   ├── hooks/
│   │   │   └── useDifyStream.ts
│   │   ├── types/
│   │   │   └── dify.ts
│   │   ├── App.tsx
│   │   ├── App.css
│   │   └── index.tsx
│   ├── package.json
│   ├── tsconfig.json
│   ├── .env
│   ├── .env.production
│   ├── Dockerfile
│   └── nginx.conf
├── nginx/
│   └── nginx.conf
├── docker-compose.yml
├── .env
├── .gitignore
└── README.md
```

### 9.1 `.gitignore`

```
# Backend
backend/target/
backend/.idea/
backend/*.iml

# Frontend
frontend/node_modules/
frontend/build/
frontend/.env.local
frontend/.env.development.local
frontend/.env.test.local
frontend/.env.production.local

# Global
.env
*.log
.DS_Store
.idea/
*.swp
*.swo
```

---

## 10. Appendix: Dify SSE Event Reference

### 10.1 Chat API Event Types

| Event | Description | Key Fields |
|-------|-------------|------------|
| `message` | LLM token chunk | `answer`, `conversation_id`, `message_id` |
| `message_end` | Final message token sent | `conversation_id`, `message_id` |
| `agent_message` | Agent reasoning step | `answer` (thought content) |
| `tool_call` | Tool execution initiated | `tool_call` (tool name, inputs) |
| `tool_response` | Tool execution completed | `tool_response` (output) |
| `workflow_started` | Workflow execution began | `workflow_run_id` |
| `node_started` | Workflow node started | `node_id`, `node_type` |
| `node_finished` | Workflow node completed | `node_id`, `outputs` |
| `workflow_finished` | Workflow execution completed | `outputs`, `status` |
| `error` | Error occurred | `error` (message), `status` |
| `ping` | Keep-alive heartbeat | None |

### 10.2 Example SSE Stream

```
event: message
data: {"event":"message","task_id":"abc-123","id":"msg-1","answer":"Hello","conversation_id":"conv-456","created_at":1700000000}

event: message
data: {"event":"message","task_id":"abc-123","id":"msg-1","answer":" there","conversation_id":"conv-456","created_at":1700000001}

event: message
data: {"event":"message","task_id":"abc-123","id":"msg-1","answer":"!","conversation_id":"conv-456","created_at":1700000002}

event: message_end
data: {"event":"message_end","task_id":"abc-123","id":"msg-1","conversation_id":"conv-456","message_id":789}

event: workflow_finished
data: {"event":"workflow_finished","task_id":"abc-123","workflow_run_id":"run-789","status":"succeeded"}
```

### 10.3 Response Modes Comparison

| Mode | Content-Type | Use Case | Latency |
|------|-------------|----------|---------|
| `streaming` | `text/event-stream` | Real-time chat, tokens visible | Lowest |
| `blocking` | `application/json` | Simple API, no streaming needed | Higher |

---

## 11. Performance Considerations

### 11.1 Spring Boot Tuning

```yaml
# application.yml
server:
  netty:
    connection-timeout: 10s

spring:
  reactor:
    netty:
      pool:
        max-connections: 500
        max-idle-time: 30s
```

### 11.2 React Performance

- Use `React.memo` for message components to prevent re-renders
- Virtualize long message lists with `react-window`
- Debounce rapid state updates during streaming

### 11.3 Scaling

| Component | Scaling Strategy |
|-----------|-----------------|
| React Frontend | Static CDN (CloudFront, Cloudflare) |
| Spring Boot | Horizontal pod autoscaling (K8s) based on CPU/memory |
| Dify AI | Use Dify Cloud (auto-scales) or self-hosted with GPU nodes |
| Nginx | Load balancer with sticky sessions for SSE |

---

*End of Document*
