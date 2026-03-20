# Anthropic Academy -- Course Notes

_Generated: 2026-03-19 19:50_

---

## Introduction to Model Context Protocol

#### [VIDEO] Welcome to the course

This video is still being processed. Please check back later and refresh the page.
Uh oh! Something went wrong, please try again.

---

#### [VIDEO] Introducing MCP

This video is still being processed. Please check back later and refresh the page.
Uh oh! Something went wrong, please try again.
Model Context Protocol (MCP) is a communication layer that provides Claude with context and tools without requiring you to write a bunch of tedious integration code. Think of it as a way to shift the burden of tool definitions and execution away from your server to specialized MCP servers.

---

#### [VIDEO] MCP clients

This video is still being processed. Please check back later and refresh the page.
Uh oh! Something went wrong, please try again.
The MCP client serves as the communication bridge between your server and MCP servers. It's your access point to all the tools that an MCP server provides, handling the message exchange and protocol details so your application doesn't have to.
One of MCP's key strengths is being transport agnostic - a fancy way of saying the client and server can communicate over different protocols depending on your setup.

---

#### [VIDEO] Project setup

2
                                    download
This video is still being processed. Please check back later and refresh the page.
Uh oh! Something went wrong, please try again.

---

#### [VIDEO] Defining tools with MCP

This video is still being processed. Please check back later and refresh the page.
Uh oh! Something went wrong, please try again.
Building an MCP server becomes much simpler when you use the official Python SDK. Instead of writing complex JSON schemas by hand, you can define tools with decorators and let the SDK handle the heavy lifting.

---

#### [VIDEO] The server inspector

This video is still being processed. Please check back later and refresh the page.
Uh oh! Something went wrong, please try again.
When building MCP servers, you need a way to test your functionality without connecting to a full application. The Python MCP SDK includes a built-in browser-based inspector that lets you debug and test your server in real-time.
First, make sure your Python environment is activated (check your project's README for the exact command). Then run the inspector with:

---

#### [QUIZ] Course satisfaction survey (Score: 0%)

---

#### [VIDEO] Implementing a client

This video is still being processed. Please check back later and refresh the page.
Uh oh! Something went wrong, please try again.
Now that we have our MCP server working, it's time to build the client side. The client is what allows our application code to communicate with the MCP server and access its functionality.
In most real-world projects, you'll either implement an MCP client or an MCP server - not both. We're building both in this project just so you can see how they work together.

---

#### [VIDEO] Defining resources

This video is still being processed. Please check back later and refresh the page.
Uh oh! Something went wrong, please try again.
Resources in MCP servers allow you to expose data to clients, similar to GET request handlers in a typical HTTP server. They're perfect for scenarios where you need to fetch information rather than perform actions.
Let's say you want to build a document mention feature where users can type @document_name to reference files. This requires two operations:

---

#### [VIDEO] Accessing resources

This video is still being processed. Please check back later and refresh the page.
Uh oh! Something went wrong, please try again.
Resources in MCP allow your server to expose information that can be directly included in prompts, rather than requiring tool calls to access data. This creates a more efficient way to provide context to AI models.
The diagram above shows how resources work: when a user types something like "What's in the @..." our code recognizes this as a resource request, sends a ReadResourceRequest to the MCP server, and gets back a ReadResourceResult with the actual content.

---

#### [VIDEO] Defining prompts

This video is still being processed. Please check back later and refresh the page.
Uh oh! Something went wrong, please try again.
Prompts in MCP servers let you define pre-built, high-quality instructions that clients can use instead of writing their own prompts from scratch. Think of them as carefully crafted templates that give better results than what users might come up with on their own.
Here's the key insight: users can already ask Claude to do most tasks directly. For example, a user could type "reformat the report.pdf in markdown" and get decent results. But they'll get much better results if you provide a thoroughly tested, specialized prompt that handles edge cases and follows best practices.

---

#### [VIDEO] Prompts in the client

This video is still being processed. Please check back later and refresh the page.
Uh oh! Something went wrong, please try again.
The final step in building our MCP client is implementing prompt functionality. This allows us to list all available prompts from the server and retrieve specific prompts with variables filled in.
The list_prompts method is straightforward. It calls the session's list prompts function and returns the prompts:

---

#### [TEXT] Final assessment on MCP

Anthropic Academy Courses		
My Profile
Sign Out
Introduction to Model Context Protocol
Course Overview
Introduction
 Welcome to the course
 Introducing MCP
 MCP clients
Hands-on with MCP servers
 Project setup
 Defining tools with MCP
 The server inspector
 Course satisfaction survey
Connecting with MCP clients
 Implementing a client
 Defining resources
 Accessing resources
 Defining prompts
 Prompts in the client
Assessment and wrap Up
 Final assessment on MCP
 MCP review
Final assessment on MCP
Open in Claude
Final Assessment Quiz on MCP
7 questions
Start
Previous - Prompts in the client
MCP review Next

---

#### [VIDEO] MCP review

This video is still being processed. Please check back later and refresh the page.
Uh oh! Something went wrong, please try again.
Now that we've built our MCP server, let's review the three core server primitives and understand when to use each one. The key insight is that each primitive is controlled by a different part of your application stack.
Tools are controlled entirely by Claude. The AI model decides when to call these functions, and the results are used directly by Claude to accomplish tasks.

---

