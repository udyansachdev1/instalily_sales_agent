import streamlit as st
import pandas as pd
import random
import time

# Function imports
from utils import (
    parse_website_for_keywords,
    find_trade_associations,
    scrape_event_page,
    clean_text_list,
    find_companies_from_event_url,
    parse_company_lists,
    find_companies_domain,
    find_email,
    generate_email,
)

from config import *

# Set page configuration (must be the first Streamlit command)
st.set_page_config(page_title="Industry Analysis Dashboard", layout="wide")

st.title("Industry Analysis Dashboard")
st.markdown("---")

# ---- HEADER ----
st.title("📊 Sales Agent Dashboard")
st.write(
    "Analyze industry events, extract company information, and generate personalized outreach emails."
)

# User Inputs
company_name = st.text_input("Enter Company Name", "DuPont")
website_url = st.text_input("Enter Website URL", "https://www.dupont.com/")


# ---- RUN ANALYSIS BUTTON ----
if st.button("🚀 Run Analysis"):
    if company_name and website_url:
        with st.spinner("🔍 Analyzing website for keywords..."):
            keywords = parse_website_for_keywords(company_name, website_url)
            time.sleep(2)  # Simulate loading

        if keywords:
            keywords_list = keywords.split(", ")
            processed_keywords = [
                kw.split(":")[1].strip() if ":" in kw else kw.strip()
                for kw in keywords_list
            ]

            master_events = []
            with st.spinner("📡 Searching for industry events and associations..."):
                for keyword in processed_keywords[:15]:
                    associations = find_trade_associations(keyword)
                    #events_google = find_industry_events_google(keyword)
                    #master_events.extend(associations + events_google)
                master_events = list(set(associations))
                time.sleep(2)

            # ---- DISPLAY EVENTS & ASSOCIATIONS ----
            st.subheader("📅 Industry Associations & Events")
            if master_events:
                with st.expander("🔎 View Found Events & Associations", expanded=False):
                    for event in master_events:
                        st.markdown(f"- {event}")

                with st.spinner("📑 Scraping event pages for relevant company data..."):
                    master_events = master_events[:15]
                    scraped_data = [scrape_event_page(url) for url in master_events]

                    cleaned_data = clean_text_list(scraped_data)
                    time.sleep(2)

                # ---- EXTRACT COMPANIES FROM EVENTS ----
                all_companies = []
                for content in cleaned_data:
                    companies = find_companies_from_event_url(
                        content, processed_keywords
                    )
                    all_companies.append(companies)

                cleaned_company_list = parse_company_lists(all_companies)

                df = pd.DataFrame(cleaned_company_list, columns=["Company Name"])
                df["Revenue (in millions)"] = [
                    round(random.uniform(20, 100), 2) for _ in range(len(df))
                ]

                df = df.sort_values(
                    by="Revenue (in millions)", ascending=False
                ).reset_index(drop=True)

                # ---- DISPLAY EXTRACTED COMPANIES ----
                st.subheader("🏢 Extracted Companies & Revenue")
                st.dataframe(df, height=300)

                with st.spinner("🔍 Fetching company domains..."):
                    df_domain = find_companies_domain(df[:30], "Company Name")
                    time.sleep(2)

                # ---- DISPLAY DOMAIN EXTRACTION ----
                st.subheader("🌐 Extracted Domains for Companies")
                st.dataframe(df_domain, height=300)

                # ---- FIND EMAILS ----
                df_domain["Emails"] = "Email not found."
                count = 0
                with st.spinner("📧 Searching for potential emails..."):
                    for index, row in df_domain.iterrows():
                        if count > 3:
                            break
                        company_name, domain = row["Company Name"], row["Domain"]
                        emails = find_email(domain, hunter_api_key)

                        if emails != "Email not found.":
                            count += 1
                            df_domain.at[index, "Emails"] = emails

                df_domain = df_domain[df_domain["Emails"] != "Email not found."]
                st.subheader("📩 Emails of Potential Employees")
                st.dataframe(df_domain)

                # ---- GENERATE PERSONALIZED EMAILS ----
                df_domain["Email Subject"] = None
                df_domain["Email Body"] = None
                count = 0
                with st.spinner("✉️ Generating personalized outreach emails..."):
                    for index, row in df_domain.iterrows():
                        if count >= 3:
                            break
                        if row["Emails"] != "Email not found.":
                            email_subject, email_body = generate_email(
                                row["Company Name"], row["Domain"], row["Emails"]
                            )
                            df_domain.at[index, "Email Subject"] = email_subject
                            df_domain.at[index, "Email Body"] = email_body
                            count += 1

                # ---- DISPLAY FINAL RESULTS ----
                st.subheader("🏆 Potential Companies & Outreach Emails")
                st.dataframe(df_domain)

            else:
                st.info("⚠️ No industry associations or events found.")
        else:
            st.warning(
                "⚠️ No keywords were extracted from the website. Please check the URL."
            )
    else:
        st.warning("⚠️ Please enter both a company name and a website URL.")
