import requests
from bs4 import BeautifulSoup
import pandas as pd
import openai
from googlesearch import search
import requests
import google.generativeai as genai
from bs4 import BeautifulSoup
from googlesearch import search
import streamlit as st
import random
import time

from config import *

client = openai.OpenAI(api_key=api_key)


def fetch_website_content(url):
    """
    Fetches cleaned text content from a website.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for script in soup(["script", "style"]):
            script.extract()
        text = soup.get_text(separator=" ", strip=True)
        return text[:3000]  # Limit to first 3000 characters
    except Exception as e:
        st.error(f"Error fetching content from {url}: {e}")
        return ""


def extract_business_keywords(content):
    """
    Extracts business-related keywords from cleaned website content using OpenAI GPT-3.5.
    """
    prompt = f"""
    Extract key business-related keywords from the following company website content.
    Focus on industries, products, services, and technology they specialize in.
    Provide a concise list of keywords:

    {content}
    """
    try:
        response = client.responses.create(
            model="gpt-3.5-turbo",  # Use the GPT-3.5-turbo model
            input=prompt,
            temperature=0.5,
        )
        # Adjust extraction depending on the API's response structure.
        if response and response.output:
            return response.output[0].content[0].text
        else:
            return "No keywords extracted."
    except Exception as e:
        st.error(f"Error extracting keywords with OpenAI: {e}")
        return ""


def parse_website_for_keywords(company_name, website_url):
    """
    Parses a company's website and extracts business-relevant keywords.
    """
    st.info(f"Fetching content for {company_name} from {website_url}...")
    content = fetch_website_content(website_url)
    if not content:
        st.error(f"No content fetched from {website_url}.")
        return ""
    # st.info("Extracting business-related keywords using OpenAI GPT-3.5...")
    keywords = extract_business_keywords(content)
    st.write(f"Extracted Overview for {company_name}:")
    st.write(keywords)
    return keywords


def find_trade_associations(keyword):
    """
    Searches for trade associations related to a keyword.
    """
    associations = []
    query = f"{keyword} trade association OR professional body"
    try:
        results = list(search(query, num_results=3))
        associations.extend(results)
    except Exception as e:
        st.error(f"Error fetching associations for {keyword}: {e}")
    return associations


def find_industry_events_google(keyword):
    """
    Searches for industry events related to a keyword.
    """
    events = []
    query = f"{keyword} industry conference OR trade show OR event"
    try:
        results = list(search(query, num_results=3))
        events.extend(results)
    except Exception as e:
        st.error(f"Error fetching events for {keyword}: {e}")
    return events


def scrape_event_page(event_url):
    """
    Scrape event webpage to extract relevant details like event description, agenda, etc.
    """
    try:
        response = requests.get(event_url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            event_content = soup.get_text()
            event_details = ""
            description_section = soup.find("section", {"class": "event-description"})
            if description_section:
                event_details += description_section.get_text(strip=True) + "\n"
            agenda_section = soup.find("section", {"class": "agenda"})
            if agenda_section:
                event_details += agenda_section.get_text(strip=True) + "\n"
            full_event_content = event_content + "\n" + event_details
            return full_event_content.strip()
        else:
            # st.error(f"Error fetching event page: {response.status_code}")
            return ""
    except Exception as e:
        # st.error(f"Error scraping event page: {e}")
        return ""


def find_companies_from_event_url(content, keywords):
    """
    Extract company names from the provided event content that match the given keywords,
    using OpenAI's GPT-3.5 Turbo model.
    """
    prompt = (
        f"Given the following content:\n\n{content}\n\n"
        f"Extract the names of companies that are related to the following keywords: {', '.join(keywords)}.\n"
        "Return the list of company names separated by newlines in plain text."
    )
    try:
        response = client.responses.create(
            model="gpt-3.5-turbo",  # Use the GPT-3.5-turbo model
            input=prompt,
            temperature=0.1,
        )
        companies_text = response.output[0].content[0].text

        # Convert the response text to a list, splitting on newline
        companies = [
            company.strip() for company in companies_text.split("\n") if company.strip()
        ]

        # Filter out companies that contain unwanted terms
        unwanted_terms = [
            "trade association",
            "professional body",
            "industry conference",
            "trade show",
            "event",
            "expo",
            "conference",
        ]
        filtered_companies = [
            company
            for company in companies
            if not any(term in company.lower() for term in unwanted_terms)
        ]

        return filtered_companies

    except Exception as e:
        st.error(f"Error extracting company names: {e}")
        return []


def get_company_details(company_name):
    """
    Fetch company details using the OpenCorporates API.
    Since OpenCorporates typically does not provide revenue or employee count,
    these fields are set to "N/A" unless available in the API response.
    """
    search_url = (
        f"https://api.opencorporates.com/v0.4/companies/search?q={company_name}"
    )
    try:
        response = requests.get(search_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            companies = data.get("results", {}).get("companies", [])
            if companies:
                company_data = companies[0].get("company", {})
                return {
                    "name": company_data.get("name", company_name),
                    "revenue": company_data.get("revenue", "N/A"),
                    "employees": company_data.get("employee_count", "N/A"),
                    "website": company_data.get("homepage_url", "N/A"),
                    "jurisdiction": company_data.get("jurisdiction_code", "N/A"),
                    "incorporation_date": company_data.get("incorporation_date", "N/A"),
                }
    except Exception as e:
        st.error(f"Error fetching company details for {company_name}: {e}")

    # Fallback output when the company is not found or an error occurred
    return {"name": company_name, "revenue": "Unknown"}


def clean_text_list(text_list):
    """Remove newline characters and empty strings from a list."""
    cleaned_list = []
    for text in text_list:
        cleaned_text = text.replace("\n", " ").strip()
        if cleaned_text:
            cleaned_list.append(cleaned_text)
    return cleaned_list


def parse_company_lists(input_data):
    """
    Parse a list of strings containing company names, breaking them into separate companies
    when newline characters are present.
    """
    companies = []
    # Flatten the list
    single_list = [item for sublist in input_data for item in sublist]
    for item in single_list:
        lines = item.split("\n")
        for line in lines:
            clean_line = line.strip()
            if clean_line.startswith("- "):
                clean_line = clean_line[2:].strip()
            # Only add short strings as valid company names
            if clean_line and len(clean_line) < 70:
                companies.append(clean_line)
    return list(set(companies))


def find_companies_domain(df, company_column):
    """
    Given a DataFrame with company names, retrieve their domains using OpenAI's GPT-4 and update the DataFrame.

    Parameters:
    - df: Pandas DataFrame containing a column with company names.
    - company_column: Name of the column containing company names.
    - openai_api_key: OpenAI API key.

    Returns:
    Updated DataFrame with a new "Domain" column.
    """

    companies = df[company_column].tolist()

    prompt = (
        "For each company in the following list, provide its official website domain:\n\n"
        + "\n".join(companies)
        + "\n\nReturn only the domain names in the format: Company Name - domain.com"
    )

    try:
        response = client.responses.create(
            model="gpt-3.5-turbo",  # Use the GPT-3.5 turbo model
            input=prompt,
            temperature=0.1,
        )

        output_text = response.output[0].content[0].text
        domain_mapping = {}

        for line in output_text.split("\n"):
            parts = line.split(" - ")
            if len(parts) == 2:
                company_name, domain = parts
                if "." in domain:
                    domain_mapping[company_name.strip()] = domain.strip()

        # Add the domain column to the DataFrame
        df["Domain"] = df[company_column].map(domain_mapping).fillna("Not Found")

        return df

    except Exception as e:
        print(f"Error fetching domains: {e}")
        df["Domain"] = "Error"
        return df


def find_email(domain, api_key):
    """
    Fetch a generic company email (like contact@, info@) using Hunter.io API.

    Parameters:
    - domain: The domain of the company (e.g., "example.com")
    - api_key: Your Hunter.io API key

    Returns:
    - A list of found emails or an error message.
    """
    url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={api_key}"
    emails_found = []

    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if "data" in data and "emails" in data["data"]:
            emails = data["data"]["emails"]
            for email in emails:
                emails_found.append(email["value"])
        if emails_found:
            return emails_found
        else:
            return "Email not found."
    else:
        return f"Error: {response.status_code}"


# Function to generate a personalized email using OpenAI
def generate_email(company_name, domain, emails):
    prompt = (
        f"Write a personalized email for a salesperson from our company, DuPont, reaching out to a company named {company_name} with the domain {domain}. "
        f"The email should explain why the salesperson from DuPont is reaching out and why this could be a great opportunity for {company_name}. "
        f"The recipient's email addresses are: {', '.join(emails)}. "
        "The tone should be friendly and professional, emphasizing the specific solutions that DuPont offers that could benefit their business.\n\n"
        # Providing more detailed information about DuPont's offerings and how they align with potential customer needs
        f"DuPont is a global multi-industrial company specializing in advanced materials, chemicals, and solutions that address challenges across various industries. "
        f"DuPont's offerings span several key sectors, including:\n"
        f"1. **Electronics and Industrial Solutions**: "
        f"DuPont provides advanced materials for semiconductor technologies, printed circuit boards, consumer electronics, and data centers. Products like advanced circuit packaging, lithographic materials, and thermal management solutions could help your company in the electronics space by increasing efficiency and performance.\n"
        f"2. **Healthcare and Medical**: "
        f"DuPont offers high-performance materials for medical devices, biopharma processing, pharmaceuticals, and healthcare packaging. For companies in the healthcare industry, DuPont’s Tyvek® for sterile medical packaging and Liveo® silicone tubing could support regulatory compliance and improve operational efficiency.\n"
        f"3. **Water and Protection**: "
        f"DuPont develops solutions for water purification, industrial wastewater treatment, desalination, and personal protective equipment (PPE) like Kevlar®, Nomex®, Tyvek®, and Styrofoam™. Your company could benefit from these solutions if you're in industries like environmental services, industrial manufacturing, or safety.\n"
        f"4. **Automotive and Advanced Mobility**: "
        f"DuPont’s specialized materials enhance electric vehicle connectivity and performance. If {company_name} is involved in automotive or mobility solutions, DuPont could help with advanced materials to drive innovation.\n"
        f"5. **Construction Materials**: "
        f"DuPont’s durable building insulation products such as Tyvek® house wraps and Styrofoam™ insulation improve energy efficiency. For companies in the construction industry, these products can help in achieving higher energy standards and meet environmental regulations.\n"
        f"With a diverse portfolio of products, DuPont offers adhesives, fabrics, fibers, nonwovens, construction materials, and advanced printing solutions, which are ideal for industries ranging from aerospace and clean energy to transportation. These materials are designed to perform in demanding environments, and DuPont is dedicated to making sure that companies like {company_name} have the best products for their needs.\n\n"
        f"The salesperson from DuPont would like to connect with {company_name} because they believe the products and solutions that DuPont offers could significantly improve the efficiency, performance, and sustainability of your operations. "
        f"We believe there is potential for collaboration, and we would love the opportunity to discuss how DuPont's expertise could benefit your company."
    )

    # Generate email content using OpenAI's GPT-3.5 Turbo
    response = client.responses.create(
        model="gpt-3.5-turbo",  # Use the GPT-3.5 turbo model
        input=prompt,
        temperature=0.5,
    )

    email_body = response.output[0].content[0].text
    subject = f"Introducing DuPont and why we're reaching out"

    return subject, email_body
