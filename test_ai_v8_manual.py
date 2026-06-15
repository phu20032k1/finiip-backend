from ai_engine import v8_run_expected_accuracy_test, suggest_journal_entry


def main():
    report = v8_run_expected_accuracy_test()
    print("AI V8 Accuracy:", report["accuracy_percent"], "%")
    print("Passed:", report["passed"], "/", report["total"])
    print("Failed:", report["failed"])
    print("\nDemo result:")
    result = suggest_journal_entry("Chạy quảng cáo Facebook Ads có VAT 10% thanh toán chuyển khoản", 11000000)
    print(result)


if __name__ == "__main__":
    main()
